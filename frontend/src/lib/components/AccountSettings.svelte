<script lang="ts">
	import { Download, UserX } from '@lucide/svelte';
	import { api, ApiError } from '$lib/api';
	import { t } from '$lib/i18n/index.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';

	/** Daten exportieren und Konto endgültig löschen. */
	const uid = $props.id();
	let password = $state('');
	let code = $state('');
	let confirmed = $state(false);
	let busy = $state(false);

	async function remove(event: SubmitEvent) {
		event.preventDefault();
		if (!confirmed || busy) return;
		busy = true;
		try {
			await api('/account/delete', {
				method: 'POST',
				body: { password, code: code.trim() || undefined }
			});
			// Alles zurücksetzen – die Sitzung gibt es nicht mehr
			window.location.assign('/login');
		} catch (error) {
			toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
		} finally {
			busy = false;
		}
	}
</script>

<section aria-labelledby="{uid}-title">
	<h2 id="{uid}-title" class="mb-1 text-base font-semibold">{t('account.title')}</h2>
	<p class="mb-3 text-sm text-muted">{t('account.exportHint')}</p>
	<a class="btn" href="/api/account/export" download>
		<Download size={16} aria-hidden="true" />{t('account.export')}
	</a>

	<h3 class="mt-8 mb-1 text-sm font-semibold text-danger">{t('account.delete')}</h3>
	<p class="mb-3 text-sm text-muted">{t('account.deleteHint')}</p>
	<form class="grid gap-3 sm:grid-cols-2" onsubmit={remove}>
		<div>
			<label class="label" for="{uid}-password">{t('account.password')}</label>
			<input
				id="{uid}-password"
				class="input"
				type="password"
				required
				autocomplete="current-password"
				maxlength="256"
				bind:value={password}
			/>
		</div>
		{#if session.user?.totp_enabled}
			<div>
				<label class="label" for="{uid}-code">{t('account.code')}</label>
				<input
					id="{uid}-code"
					class="input"
					required
					autocomplete="one-time-code"
					maxlength="20"
					bind:value={code}
				/>
			</div>
		{/if}
		<label class="flex items-center gap-2 text-sm sm:col-span-2">
			<input type="checkbox" bind:checked={confirmed} />{t('account.confirm')}
		</label>
		<div>
			<button type="submit" class="btn btn-danger" disabled={!confirmed || busy}>
				<UserX size={16} aria-hidden="true" />{t('account.deleteButton')}
			</button>
		</div>
	</form>
</section>
