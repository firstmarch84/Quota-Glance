function usageURL(url) {
  try { const u=new URL(url); return u.origin==='https://claude.ai' && (u.pathname.replace(/\/$/,'')==='/settings/usage' || /^#\/?settings\/usage\/?(?:\?|$)/.test(u.hash)); }
  catch { return false; }
}
function routeAccount(sender) { return usageURL(sender.url) ? 'claude' : null; }
