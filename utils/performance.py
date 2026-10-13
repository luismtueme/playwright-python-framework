"""Page load metrics from the browser Performance APIs.

LCP and CLS are Chromium-only, so they're absent in other browsers. CI machines are
noisy, so budgets should catch regressions rather than measure absolute speed.
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Page

_MEASURE = """
async () => {
  const [nav] = performance.getEntriesByType('navigation');
  if (!nav) throw new Error('No navigation timing entry: measure right after page.goto()');
  const observe = (type, reduce) => new Promise((resolve) => {
    if (!PerformanceObserver.supportedEntryTypes.includes(type)) return resolve(undefined);
    const observer = new PerformanceObserver((list) => {
      observer.disconnect();
      resolve(reduce(list.getEntries()));
    });
    observer.observe({ type, buffered: true });
    setTimeout(() => {
      observer.disconnect();
      resolve(reduce([]));
    }, 250);
  });
  const lcp = await observe('largest-contentful-paint', (entries) => entries.at(-1)?.startTime ?? 0);
  const cls = await observe('layout-shift', (entries) =>
    entries.reduce((sum, entry) => (entry.hadRecentInput ? sum : sum + entry.value), 0));
  return {
    ttfb: Math.round(nav.responseStart - nav.startTime),
    domContentLoaded: Math.round(nav.domContentLoadedEventEnd - nav.startTime),
    load: Math.round(nav.loadEventEnd - nav.startTime),
    ...(lcp === undefined ? {} : { lcp: Math.round(lcp) }),
    ...(cls === undefined ? {} : { cls: Number(cls.toFixed(4)) }),
  };
}
"""


def measure_page(page: Page) -> dict[str, float]:
    """Measure the current page. Call after navigation; waits for the load event."""
    page.wait_for_load_state("load")
    metrics = page.evaluate(_MEASURE)
    if not isinstance(metrics, dict):
        raise RuntimeError("Performance measurement did not return an object")
    return {str(key): float(value) for key, value in metrics.items()}


def over_budget(metrics: dict[str, float], budget: dict[str, Any]) -> list[str]:
    """Metrics over their budget, as readable lines. Empty when everything is within budget."""
    lines: list[str] = []
    for metric, limit in budget.items():
        if metric.startswith("$"):
            continue
        value = metrics.get(metric)
        if value is not None and float(value) > float(limit):
            lines.append(f"{metric} {float(value)} > budget {limit}")
    return lines
