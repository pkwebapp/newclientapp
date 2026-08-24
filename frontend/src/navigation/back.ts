export function goBackOr(router: any, fallback: string): void {
  try {
    if (router.canGoBack()) {
      router.back();
      return;
    }
  } catch {
    // Fall through to an explicit route when history is unavailable.
  }
  router.replace(fallback as any);
}
