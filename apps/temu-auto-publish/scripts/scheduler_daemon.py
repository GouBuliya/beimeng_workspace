#!/usr/bin/env python3
"""
@PURPOSE: 定时任务守护进程 - 基于APScheduler实现定时执行工作流
@OUTLINE:
  - class SchedulerDaemon: 定时任务守护进程
  - def start(): 启动守护进程
  - def stop(): 停止守护进程
  - def status(): 查看状态
  - def add_job_from_config(): 从配置添加任务
  - def main(): 主入口
@GOTCHAS:
  - 同一时间只运行一个工作流任务(使用锁机制)
  - 需要正确处理信号(SIGTERM/SIGINT)
  - PID文件管理很重要
@DEPENDENCIES:
  - 外部: apscheduler, daemon(可选)
  - 内部: run_production
@RELATED: run_production.py
"""

import argparse
import asyncio
import atexit
import json
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings


class SchedulerDaemon:
    """定时任务守护进程.
    
    使用APScheduler管理定时任务,支持:
    - Cron表达式调度
    - 并发控制(同一时间只运行一个任务)
    - 任务日志记录
    - 守护进程模式
    
    Attributes:
        config_path: 配置文件路径
        pid_file: PID文件路径
        log_file: 日志文件路径
        scheduler: APScheduler实例
        
    Examples:
        >>> daemon = SchedulerDaemon()
        >>> daemon.start()
    """
    
    def __init__(
        self,
        config_path: Optional[Path] = None,
        pid_file: Optional[Path] = None,
        log_file: Optional[Path] = None
    ):
        """初始化守护进程.
        
        Args:
            config_path: 配置文件路径
            pid_file: PID文件路径
            log_file: 日志文件路径
        """
        self.config_path = config_path or project_root / "config" / "production.yaml"
        self.pid_file = pid_file or project_root / "data" / "scheduler.pid"
        self.log_file = log_file or project_root / "data" / "logs" / "scheduler.log"
        
        # 确保目录存在
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载配置
        self.config = self._load_config()
        
        # 创建调度器
        self.scheduler = BlockingScheduler()
        
        # 任务执行锁(防止并发)
        self.job_lock_file = project_root / "data" / "job.lock"
        
        logger.info("定时任务守护进程已初始化")
    
    def _load_config(self) -> Dict:
        """加载配置文件.
        
        Returns:
            配置字典
        """
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}")
            return {}
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            logger.info(f"✓ 已加载配置文件: {self.config_path}")
            return config or {}
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {}
    
    def _is_job_running(self) -> bool:
        """检查是否有任务正在运行.
        
        Returns:
            是否有任务运行中
        """
        if not self.job_lock_file.exists():
            return False
        
        try:
            # 检查锁文件中的PID是否还在运行
            with open(self.job_lock_file, "r") as f:
                pid = int(f.read().strip())
            
            # 检查进程是否存在
            try:
                os.kill(pid, 0)  # 发送信号0只检查进程是否存在
                return True
            except OSError:
                # 进程不存在,清理锁文件
                self.job_lock_file.unlink()
                return False
        except Exception as e:
            logger.warning(f"检查任务锁失败: {e}")
            return False
    
    def _acquire_lock(self) -> bool:
        """获取任务锁.
        
        Returns:
            是否成功获取锁
        """
        if self._is_job_running():
            logger.warning("已有任务正在运行,跳过本次执行")
            return False
        
        try:
            with open(self.job_lock_file, "w") as f:
                f.write(str(os.getpid()))
            return True
        except Exception as e:
            logger.error(f"获取任务锁失败: {e}")
            return False
    
    def _release_lock(self):
        """释放任务锁."""
        try:
            if self.job_lock_file.exists():
                self.job_lock_file.unlink()
        except Exception as e:
            logger.error(f"释放任务锁失败: {e}")
    
    def execute_job(self, job_config: Dict):
        """执行任务.
        
        Args:
            job_config: 任务配置
        """
        job_name = job_config.get("name", "unknown")
        logger.info(f"=" * 60)
        logger.info(f"开始执行任务: {job_name}")
        logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"=" * 60)
        
        # 检查任务是否启用
        if not job_config.get("enabled", False):
            logger.info(f"任务 {job_name} 未启用,跳过")
            return
        
        # 获取锁
        if not self._acquire_lock():
            return
        
        try:
            # 构建命令
            cmd = [
                sys.executable,
                str(project_root / "scripts" / "run_production.py"),
                job_config["input_path"]
            ]
            
            # 添加参数
            if "input_type" in job_config:
                cmd.extend(["--type", job_config["input_type"]])
            
            if "staff_name" in job_config and job_config["staff_name"]:
                cmd.extend(["--staff-name", job_config["staff_name"]])
            
            if not job_config.get("enable_batch_edit", True):
                cmd.append("--no-batch-edit")
            
            if not job_config.get("enable_publish", True):
                cmd.append("--no-publish")
            
            if not job_config.get("use_ai_titles", True):
                cmd.append("--no-ai-titles")
            
            logger.info(f"执行命令: {' '.join(cmd)}")
            
            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=project_root
            )
            
            # 记录输出
            if result.stdout:
                logger.info(f"标准输出:\n{result.stdout}")
            if result.stderr:
                logger.warning(f"错误输出:\n{result.stderr}")
            
            # 检查退出码
            if result.returncode == 0:
                logger.success(f"✓ 任务 {job_name} 执行成功")
            else:
                logger.error(f"✗ 任务 {job_name} 执行失败 (退出码: {result.returncode})")
        
        except Exception as e:
            logger.error(f"执行任务 {job_name} 异常: {e}")
            logger.exception("详细错误:")
        
        finally:
            # 释放锁
            self._release_lock()
            
            logger.info(f"=" * 60)
            logger.info(f"任务 {job_name} 执行完成")
            logger.info(f"=" * 60 + "\n")
    
    def add_jobs_from_config(self):
        """从配置文件添加所有任务."""
        scheduler_config = self.config.get("scheduler", {})
        jobs = scheduler_config.get("jobs", [])
        
        if not jobs:
            logger.warning("配置文件中没有定义任何任务")
            return
        
        for job_config in jobs:
            job_name = job_config.get("name")
            if not job_name:
                logger.warning("跳过未命名的任务")
                continue
            
            if not job_config.get("enabled", False):
                logger.info(f"任务 {job_name} 未启用,跳过添加")
                continue
            
            schedule = job_config.get("schedule")
            if not schedule:
                logger.warning(f"任务 {job_name} 未配置调度表达式,跳过")
                continue
            
            try:
                # 解析Cron表达式
                trigger = CronTrigger.from_crontab(schedule)
                
                # 添加任务
                self.scheduler.add_job(
                    func=self.execute_job,
                    trigger=trigger,
                    args=[job_config],
                    id=job_name,
                    name=job_name,
                    replace_existing=True
                )
                
                logger.info(f"✓ 已添加任务: {job_name} (调度: {schedule})")
            
            except Exception as e:
                logger.error(f"添加任务 {job_name} 失败: {e}")
    
    def start(self, daemon_mode: bool = False):
        """启动守护进程.
        
        Args:
            daemon_mode: 是否以守护进程模式运行
        """
        # 检查是否已经在运行
        if self.is_running():
            logger.error("守护进程已在运行")
            print("✗ 守护进程已在运行")
            sys.exit(1)
        
        # 配置日志
        logger.remove()  # 移除默认处理器
        logger.add(
            self.log_file,
            rotation="100 MB",
            retention="30 days",
            encoding="utf-8",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
        )
        logger.add(sys.stdout, level="INFO")  # 也输出到控制台
        
        logger.info("=" * 60)
        logger.info("Temu自动发布系统 - 定时任务守护进程")
        logger.info("=" * 60)
        logger.info(f"PID文件: {self.pid_file}")
        logger.info(f"日志文件: {self.log_file}")
        logger.info(f"配置文件: {self.config_path}")
        
        # 保存PID
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))
        
        # 注册清理函数
        atexit.register(self.cleanup)
        
        # 注册信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # 添加任务
        self.add_jobs_from_config()
        
        # 显示任务列表
        jobs = self.scheduler.get_jobs()
        if jobs:
            logger.info(f"\n已加载 {len(jobs)} 个任务:")
            for job in jobs:
                logger.info(f"  - {job.name}: {job.trigger}")
        else:
            logger.warning("没有加载任何任务")
            print("⚠ 没有加载任何任务,请检查配置文件")
            sys.exit(1)
        
        logger.info("\n✓ 守护进程已启动,等待任务调度...")
        print(f"✓ 守护进程已启动 (PID: {os.getpid()})")
        print(f"日志文件: {self.log_file}")
        print("使用 Ctrl+C 或 'python scripts/scheduler_daemon.py stop' 停止")
        
        try:
            # 启动调度器
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("接收到退出信号,正在关闭...")
            self.stop()
    
    def stop(self):
        """停止守护进程."""
        if not self.is_running():
            logger.warning("守护进程未运行")
            print("⚠ 守护进程未运行")
            return
        
        try:
            # 读取PID
            with open(self.pid_file, "r") as f:
                pid = int(f.read().strip())
            
            # 发送SIGTERM信号
            logger.info(f"正在停止守护进程 (PID: {pid})...")
            os.kill(pid, signal.SIGTERM)
            
            # 等待进程退出
            import time
            for _ in range(10):
                if not self.is_running():
                    break
                time.sleep(0.5)
            
            if self.is_running():
                logger.warning("进程未响应SIGTERM,尝试SIGKILL...")
                os.kill(pid, signal.SIGKILL)
            
            logger.info("✓ 守护进程已停止")
            print("✓ 守护进程已停止")
        
        except Exception as e:
            logger.error(f"停止守护进程失败: {e}")
            print(f"✗ 停止守护进程失败: {e}")
    
    def status(self):
        """查看守护进程状态."""
        if not self.is_running():
            print("✗ 守护进程未运行")
            return
        
        try:
            with open(self.pid_file, "r") as f:
                pid = int(f.read().strip())
            
            print(f"✓ 守护进程正在运行 (PID: {pid})")
            print(f"PID文件: {self.pid_file}")
            print(f"日志文件: {self.log_file}")
            
            # 检查任务锁
            if self._is_job_running():
                print("⚠ 当前有任务正在执行")
            else:
                print("空闲中,等待下一个调度时间")
            
            # 显示最近的日志
            if self.log_file.exists():
                print(f"\n最近的日志 (最后10行):")
                with open(self.log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in lines[-10:]:
                        print(f"  {line.rstrip()}")
        
        except Exception as e:
            print(f"✗ 查看状态失败: {e}")
    
    def is_running(self) -> bool:
        """检查守护进程是否正在运行.
        
        Returns:
            是否运行中
        """
        if not self.pid_file.exists():
            return False
        
        try:
            with open(self.pid_file, "r") as f:
                pid = int(f.read().strip())
            
            # 检查进程是否存在
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            # 进程不存在或PID文件损坏
            if self.pid_file.exists():
                self.pid_file.unlink()
            return False
    
    def cleanup(self):
        """清理资源."""
        logger.info("清理资源...")
        
        # 关闭调度器
        if hasattr(self, "scheduler") and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        
        # 删除PID文件
        if self.pid_file.exists():
            self.pid_file.unlink()
        
        # 释放任务锁
        self._release_lock()
    
    def _signal_handler(self, signum, frame):
        """信号处理函数.
        
        Args:
            signum: 信号编号
            frame: 当前栈帧
        """
        logger.info(f"接收到信号 {signum},正在退出...")
        self.cleanup()
        sys.exit(0)


def main():
    """主入口函数."""
    parser = argparse.ArgumentParser(
        description="Temu自动发布系统 - 定时任务守护进程"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # start命令
    start_parser = subparsers.add_parser("start", help="启动守护进程")
    start_parser.add_argument(
        "--config",
        type=Path,
        help="配置文件路径"
    )
    start_parser.add_argument(
        "--daemon",
        action="store_true",
        help="以守护进程模式运行(后台运行)"
    )
    
    # stop命令
    subparsers.add_parser("stop", help="停止守护进程")
    
    # status命令
    subparsers.add_parser("status", help="查看守护进程状态")
    
    # restart命令
    subparsers.add_parser("restart", help="重启守护进程")
    
    args = parser.parse_args()
    
    # 创建守护进程实例
    daemon = SchedulerDaemon(config_path=args.config if hasattr(args, "config") else None)
    
    # 执行命令
    if args.command == "start":
        daemon.start(daemon_mode=args.daemon if hasattr(args, "daemon") else False)
    elif args.command == "stop":
        daemon.stop()
    elif args.command == "status":
        daemon.status()
    elif args.command == "restart":
        print("正在重启守护进程...")
        daemon.stop()
        import time
        time.sleep(2)
        daemon.start()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

