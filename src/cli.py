"""CLI entry point for bird-photo-processor."""

import sys
from pathlib import Path

import click

from src.processor.engine import ProcessingEngine
from src.utils.config import Config, get_config
from src.utils.report import export_report


@click.group()
@click.version_option(version="0.1.0")
@click.option("--config", type=click.Path(), help="Config file path")
@click.pass_context
def cli(ctx, config):
    """Bird Photo Processor - 拍鸟照片过滤器"""
    ctx.ensure_object(dict)
    if config:
        ctx.obj["config"] = Config.load(Path(config))
    else:
        ctx.obj["config"] = get_config()


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Simulate without making changes")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--parallel", "-p", type=int, help="Number of parallel workers")
@click.option("--skip-dedup", is_flag=True, help="Skip deduplication")
@click.option("--skip-quality", is_flag=True, help="Skip quality assessment")
@click.option("--skip-recognize", is_flag=True, help="Skip bird recognition")
@click.option("--auto-delete", is_flag=True, help="Auto-delete low quality images")
@click.option("--export", "-e", type=click.Path(), help="Export report to file (json/csv/html/md)")
@click.pass_context
def scan(
    ctx,
    path,
    dry_run,
    verbose,
    parallel,
    skip_dedup,
    skip_quality,
    skip_recognize,
    auto_delete,
    export,
):
    """Scan directory for bird photos and process them."""
    config = ctx.obj["config"]

    # Override config with CLI options
    if parallel:
        config.performance.parallel_workers = parallel

    # Set up logging
    if verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)

    click.echo(f"🔍 扫描目录: {path}")
    click.echo(f"   模拟运行: {dry_run}")
    click.echo("")

    engine = ProcessingEngine(config)
    result = engine.process(
        Path(path), skip_dedup=skip_dedup, skip_quality=skip_quality, skip_recognize=skip_recognize
    )

    # Print summary
    click.echo(engine.get_summary(result))

    # Show duplicates in detail
    if result.duplicate_groups and not skip_dedup:
        click.echo("")
        click.echo("📋 重复照片组详情:")
        for group in result.duplicate_groups:
            best = group.best_image
            if best:
                click.echo(f"\n组 {group.group_id}:")
                for img in group.images:
                    quality_str = f"{img.quality_score:.1f}" if img.quality_score else "N/A"
                    marker = "⭐" if img.path == best.path else "  "
                    click.echo(f"  {marker} {img.filename} [质量: {quality_str}]")

    # Handle auto-delete
    if auto_delete and not dry_run and result.low_quality_images:
        click.echo(f"\n🗑️ 将删除 {len(result.low_quality_images)} 张低质量照片")

        if click.confirm("确认删除?"):
            from src.processor.organizer import FileOrganizer

            organizer = FileOrganizer(output_dir=Path("."), use_trash=config.file.use_trash)
            deleted = organizer.delete_files(result.low_quality_images)
            click.echo(f"已删除 {len(deleted)} 张照片")

    # Export report
    if export:
        output_path = Path(export)
        try:
            export_report(result, output_path)
            click.echo(f"\n📄 报告已导出: {output_path.absolute()}")
        except Exception as e:
            click.echo(f"导出报告失败: {e}", err=True)


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.argument("output_dir", type=click.Path())
@click.option("--dry-run", is_flag=True, default=True, help="Simulate without making changes")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--by-species/--no-species", default=True, help="Organize by species")
@click.option("--by-date/--no-date", default=True, help="Organize by date")
@click.pass_context
def organize(ctx, path, output_dir, dry_run, verbose, by_species, by_date):
    """Organize photos into species/date directories."""
    config = ctx.obj["config"]

    # Override config
    config.organize.by_species = by_species
    config.organize.by_date = by_date
    config.organize.enabled = True

    click.echo(f"📁 整理照片: {path}")
    click.echo(f"   输出目录: {output_dir}")
    click.echo(f"   模拟运行: {dry_run}")
    click.echo("")

    engine = ProcessingEngine(config)
    result = engine.process_organized(Path(path), Path(output_dir), dry_run=dry_run)

    click.echo(engine.get_summary(result))

    if not dry_run:
        click.echo(f"\n📤 已移动: {len(result.moved_images)} 张")
        click.echo(f"🗑️ 已删除: {len(result.deleted_images)} 张")


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, default=True, help="Simulate without making changes")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="duplicates",
    help="Output directory for groups",
)
@click.option("--threshold", "-t", type=float, help="Similarity threshold override")
@click.pass_context
def group(ctx, path, dry_run, output_dir, threshold):
    """Group duplicate photos into directories (instead of deleting)."""
    config = ctx.obj["config"]

    # Override config
    if threshold:
        config.dedup.similarity_threshold = threshold
    config.dedup.mode = "group"
    config.dedup.group_output_dir = output_dir

    click.echo(f"📁 分组重复照片: {path}")
    click.echo(f"   输出目录: {output_dir}")
    click.echo(f"   模拟运行: {dry_run}")
    click.echo(f"   相似度阈值: {config.dedup.similarity_threshold}")
    click.echo("")

    engine = ProcessingEngine(config)

    # Scan images first
    images = engine.scanner.scan(Path(path))

    if not images:
        click.echo("未找到图片")
        return

    click.echo(f"找到 {len(images)} 张图片")

    # Assess quality for sorting
    images = engine.quality.assess_batch(images)

    # Recognize species
    if config.recognizer.enabled:
        images = engine.recognizer.recognize_batch(images)

    # Group duplicates
    click.echo("正在分组重复照片...")
    moves = engine.dedup.group_duplicates(images, Path(path).parent, dry_run=dry_run)

    if moves:
        click.echo(f"\n{'将复制' if dry_run else '已复制'}: {len(moves)} 张照片到分组目录")
    else:
        click.echo("\n未找到重复照片")


@cli.command()
@click.option("--dry-run", is_flag=True, help="Simulate without making changes")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def device(dry_run, verbose):
    """Scan connected storage devices."""
    click.echo("📷 扫描已连接的存储设备...")

    # macOS: List mounted volumes
    if sys.platform == "darwin":
        import subprocess

        result = subprocess.run(
            ["diskutil", "list", "-plist", "external"], capture_output=True, text=True
        )

        import plistlib

        try:
            data = plistlib.loads(result.stdout.encode())
            volumes = data.get("VolumesFromBackingStoreDevices", [])

            if not volumes:
                click.echo("未找到外接存储设备")
                return

            click.echo(f"找到 {len(volumes)} 个外接设备:")
            for vol in volumes:
                mount_point = f"/Volumes/{vol}"
                click.echo(f"  - {vol} -> {mount_point}")

                # Scan this volume
                if Path(mount_point).exists():
                    if click.confirm(f"扫描 {mount_point}?"):
                        ctx = click.get_current_context()
                        ctx.invoke(scan, path=mount_point, dry_run=dry_run, verbose=verbose)

        except Exception as e:
            click.echo(f"获取设备列表失败: {e}")
    else:
        click.echo("当前仅支持 macOS 设备扫描")


@cli.command()
@click.argument("path", required=False, type=click.Path(exists=True))
@click.option("--help", is_flag=True, help="Show help message")
def gui(path, help):
    """Open GUI window for photo management."""
    if help:
        click.echo("Usage: python -m src.cli gui [PATH]")
        click.echo("")
        click.echo("Open a visual window to:")
        click.echo("  - Browse and preview photos")
        click.echo("  - View quality scores (clarity, focus, sharpness)")
        click.echo("  - Select and delete photos")
        click.echo("  - Lock photos from batch operations")
        click.echo("  - Filter by quality threshold or species")
        return

    try:
        from src.gui.main import run_gui

        run_gui(path if path else None)
    except ImportError as e:
        click.echo("Error: PyQt6 is not installed.", err=True)
        click.echo("Please install it with: pip install PyQt6", err=True)
        sys.exit(1)


@cli.command()
def watch():
    """Watch for new devices and auto-scan."""
    click.echo("👀 监听新设备插入...")
    click.echo("按 Ctrl+C 停止")

    # TODO: Implement device watching
    click.echo("\n⚠️ 设备监听功能开发中...")


@cli.group()
def config_cmd():
    """Manage configuration."""
    pass


@config_cmd.command("show")
def config_show():
    """Show current configuration."""
    config = get_config()

    click.echo("📋 当前配置:")
    click.echo("")

    # Dedup
    click.echo("[去重]")
    click.echo(f"  相似度阈值: {config.dedup.similarity_threshold}")
    click.echo(f"  哈希算法: {config.dedup.hash_algorithm}")
    click.echo(f"  鸟种辅助判断: {config.dedup.species_aware}")
    click.echo(f"  最小时间间隔: {config.dedup.min_time_interval} 秒")
    click.echo(f"  保留最好数量: {config.dedup.keep_best_count}")
    click.echo(f"  保留备份: {config.dedup.keep_backup}")
    click.echo("")

    # Quality
    click.echo("[质量评估]")
    click.echo(f"  评估模式: {config.quality.mode} (basic/advanced)")
    click.echo(f"  阈值: {config.quality.threshold}")
    click.echo(f"  启用: {config.quality.enabled}")
    click.echo("")

    # Recognizer
    click.echo("[鸟类识别]")
    click.echo(f"  类型: {config.recognizer.type}")
    click.echo(f"  模型: {config.recognizer.model}")
    click.echo(f"  启用: {config.recognizer.enabled}")
    click.echo("")

    # Organize
    click.echo("[文件整理]")
    click.echo(f"  按物种分类: {config.organize.by_species}")
    click.echo(f"  按日期分类: {config.organize.by_date}")
    click.echo(f"  最低保留质量: {config.organize.min_quality_for_keep}")
    click.echo(f"  每种最少保留: {config.organize.min_species_images} 张")


@config_cmd.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set configuration value."""
    config = get_config()

    # Map keys to config paths
    key_map = {
        "quality.threshold": ("quality", "threshold", float),
        "dedup.threshold": ("dedup", "similarity_threshold", float),
        "dedup.algorithm": ("dedup", "hash_algorithm", str),
        "dedup.species_aware": ("dedup", "species_aware", lambda x: x.lower() == "true"),
        "dedup.time_interval": ("dedup", "min_time_interval", int),
        "dedup.keep_backup": ("dedup", "keep_backup", lambda x: x.lower() == "true"),
        "organize.by_species": ("organize", "by_species", lambda x: x.lower() == "true"),
        "organize.by_date": ("organize", "by_date", lambda x: x.lower() == "true"),
        "organize.min_quality": ("organize", "min_quality_for_keep", float),
        "organize.min_species": ("organize", "min_species_images", int),
    }

    if key not in key_map:
        click.echo(f"未知配置项: {key}")
        click.echo("可用配置项: " + ", ".join(key_map.keys()))
        return

    section, attr, converter = key_map[key]
    section_obj = getattr(config, section)
    setattr(section_obj, attr, converter(value))

    config.save()
    click.echo(f"✅ 已设置 {key} = {value}")


@config_cmd.command("reset")
def config_reset():
    """Reset configuration to defaults."""
    if click.confirm("确定重置所有配置?"):
        config = Config()
        config.save()
        click.echo("✅ 配置已重置为默认值")


@cli.command()
def status():
    """Show processing status and cache info."""
    config = get_config()

    click.echo("📊 状态信息:")
    click.echo(f"  配置文件: {Config.get_config_path()}")
    click.echo(f"  缓存目录: {config.cache.dir}")
    click.echo(f"  缓存启用: {config.cache.enabled}")
    click.echo(f"  并行工作数: {config.performance.parallel_workers}")


if __name__ == "__main__":
    cli()
