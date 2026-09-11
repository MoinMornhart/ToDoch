import { t } from '$lib/i18n/index.svelte';

/** Genauer Grund, wenn der Anbieter die Anmeldung ablehnt (aus ?reason=… nach dem Rücksprung). */
export function oauthReason(reason: string | null, provider: string | null): string {
	if (!reason) return '';
	if (reason === 'invalid_client' || reason === 'unauthorized_client') {
		return t('oauth.reasonClient');
	}
	if (reason === 'invalid_grant' || reason === 'redirect_uri_mismatch') {
		const name = provider === 'microsoft' ? 'microsoft' : 'google';
		return t('oauth.reasonRedirect', {
			uri: `${window.location.origin}/api/mail/oauth/${name}/callback`
		});
	}
	if (reason === 'invalid_scope' || reason === 'access_denied') return t('oauth.reasonPermission');
	return t('oauth.reasonOther', { code: reason });
}
