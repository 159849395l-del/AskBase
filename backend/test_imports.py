"""Test crawler module imports"""
import sys
sys.path.insert(0, r"D:\claude_test\LangChainRAG项目\backend")

try:
    from app.crawler.config import load_crawler_config, CrawlerDbConfig
    print("OK: config.py")
except Exception as e:
    print(f"FAIL: config.py: {e}")

try:
    from app.crawler.utils import normalize, is_same_domain, url_hash
    print("OK: utils.py")
except Exception as e:
    print(f"FAIL: utils.py: {e}")

try:
    from app.crawler.models import CrawlTask, TaskStatus, get_crawler_session_factory
    print("OK: models.py")
except Exception as e:
    print(f"FAIL: models.py: {e}")

try:
    from app.crawler.sse_publisher import publish_status, subscribe
    print("OK: sse_publisher.py")
except Exception as e:
    print(f"FAIL: sse_publisher.py: {e}")

try:
    from app.crawler.engine.fetcher import StaticHttpFetcher, PlaywrightFetcher, CrawlerRouter
    print("OK: fetcher.py")
except Exception as e:
    print(f"FAIL: fetcher.py: {e}")

try:
    from app.crawler.engine.html_cleaner import HtmlCleaner
    print("OK: html_cleaner.py")
except Exception as e:
    print(f"FAIL: html_cleaner.py: {e}")

try:
    from app.crawler.engine.rate_limiter import RateLimiter
    print("OK: rate_limiter.py")
except Exception as e:
    print(f"FAIL: rate_limiter.py: {e}")

try:
    from app.crawler.engine.robots_policy import RobotsPolicy
    print("OK: robots_policy.py")
except Exception as e:
    print(f"FAIL: robots_policy.py: {e}")

try:
    from app.crawler.engine.planner import execute_planning
    print("OK: planner.py")
except Exception as e:
    print(f"FAIL: planner.py: {e}")

try:
    from app.crawler.engine.discovery import execute_discovery
    print("OK: discovery.py")
except Exception as e:
    print(f"FAIL: discovery.py: {e}")

try:
    from app.crawler.engine.crawler import execute_crawling
    print("OK: crawler.py")
except Exception as e:
    print(f"FAIL: crawler.py: {e}")

try:
    from app.crawler.engine.extractor import execute_extracting
    print("OK: extractor.py")
except Exception as e:
    print(f"FAIL: extractor.py: {e}")

try:
    from app.crawler.engine.verifier import execute_verifying
    print("OK: verifier.py")
except Exception as e:
    print(f"FAIL: verifier.py: {e}")

try:
    from app.crawler.engine.aggregator import execute_aggregating
    print("OK: aggregator.py")
except Exception as e:
    print(f"FAIL: aggregator.py: {e}")

try:
    from app.crawler.engine.orchestrator import submit_task
    print("OK: orchestrator.py")
except Exception as e:
    print(f"FAIL: orchestrator.py: {e}")

try:
    from app.crawler.api.tasks import router as task_router
    print("OK: api/tasks.py")
except Exception as e:
    print(f"FAIL: api/tasks.py: {e}")

try:
    from app.crawler.api.results import router as result_router
    print("OK: api/results.py")
except Exception as e:
    print(f"FAIL: api/results.py: {e}")

try:
    from app.crawler.api.schedule import router as schedule_router
    print("OK: api/schedule.py")
except Exception as e:
    print(f"FAIL: api/schedule.py: {e}")

print("\n=== All tests done ===")
