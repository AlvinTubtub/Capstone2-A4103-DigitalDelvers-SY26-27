export const TRANSPORT_DELAY_MS = 1000;

export function isTransportNoDocument(attempt) {
  return attempt.main_document_response_received === false
    && attempt.app_dom_available === false
    && attempt.assertions_executed === false
    && attempt.http_status == null
    && Boolean(attempt.browser_navigation_error);
}

export async function runBoundedTransportCase(runAttempt, wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))) {
  const attempts = [await runAttempt(1)];
  const retryAllowed = isTransportNoDocument(attempts[0]);
  if (retryAllowed) {
    await wait(TRANSPORT_DELAY_MS);
    attempts.push(await runAttempt(2));
  }
  const final = attempts.at(-1);
  return {
    attempts,
    final,
    transport_attempt_count: attempts.length,
    transport_retry_used: retryAllowed,
    first_attempt_transport_status: retryAllowed ? 'TRANSPORT_NO_DOCUMENT' : attempts[0].transport_status,
  };
}
