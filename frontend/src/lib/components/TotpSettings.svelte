<script lang="ts">
	import { Copy, ShieldCheck } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import type { TotpSetup, TotpStatus } from '$lib/types';

	const uid = $props.id();
	let status = $state<TotpStatus | null>(null);
	let setup = $state<TotpSetup | null>(null);
	let codes = $state<string[] | null>(null);
	let password = $state('');
	let code = $state('');
	let busy = $state(false);

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	async function load() {
		try {
			status = await api<TotpStatus>('/auth/totp');
			if (session.user) session.user.totp_enabled = status.enabled;
		} catch (error) {
			report(error);
		}
	}

	onMount(load);

	async function run(action: () => Promise<void>) {
		busy = true;
		try {
			await action();
		} catch (error) {
			report(error);
		} finally {
			busy = false;
		}
	}

	const start = (event: SubmitEvent) => {
		event.preventDefault();
		return run(async () => {
			setup = await api<TotpSetup>('/auth/totp/setup', { method: 'POST', body: { password } });
			password = '';
			code = '';
		});
	};

	const confirm = (event: SubmitEvent) => {
		event.preventDefault();
		return run(async () => {
			const result = await api<{ recovery_codes: string[] }>('/auth/totp/confirm', {
				method: 'POST',
				body: { code: code.trim() }
			});
			codes = result.recovery_codes;
			setup = null;
			code = '';
			toasts.show(t('totp.enabled'));
			await load();
		});
	};

	const regenerate = (event: SubmitEvent) => {
		event.preventDefault();
		return run(async () => {
			const result = await api<{ recovery_codes: string[] }>('/auth/totp/recovery-codes', {
				method: 'POST',
				body: { password }
			});
			codes = result.recovery_codes;
			password = '';
			await load();
		});
	};

	const disable = (event: SubmitEvent) => {
		event.preventDefault();
		return run(async () => {
			await api('/auth/totp/disable', {
				method: 'POST',
				body: { password, code: code.trim() }
			});
			password = '';
			code = '';
			toasts.show(t('totp.disabled'));
			await load();
		});
	};

	async function copyCodes() {
		if (!codes) return;
		try {
			await navigator.clipboard.writeText(codes.join('\n'));
			toasts.show(t('totp.copied'));
		} catch {
			toasts.error(t('error.generic'));
		}
	}

	function formatDate(value: string): string {
		return new Intl.DateTimeFormat(i18n.locale, { dateStyle: 'medium' }).format(new Date(value));
	}
</script>

<section aria-labelledby="{uid}-title">
	<h2 id="{uid}-title" class="mb-1 flex items-center gap-2 text-base font-semibold">
		<ShieldCheck size={18} aria-hidden="true" />{t('totp.title')}
	</h2>
	<p class="mb-3 text-sm text-muted">{t('totp.intro')}</p>

	{#if codes}
		<div class="mb-4 rounded-xl border border-accent bg-raised p-4" role="status">
			<p class="text-sm font-semibold">{t('totp.codesTitle')}</p>
			<p class="mb-3 text-xs text-muted">{t('totp.codesHint')}</p>
			<ul class="mb-3 grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-sm">
				{#each codes as recovery (recovery)}<li data-testid="recovery-code">{recovery}</li>{/each}
			</ul>
			<div class="flex flex-wrap gap-2">
				<button type="button" class="btn" onclick={copyCodes}>
					<Copy size={14} aria-hidden="true" />{t('totp.copy')}
				</button>
				<button type="button" class="btn btn-primary" onclick={() => (codes = null)}>
					{t('totp.done')}
				</button>
			</div>
		</div>
	{/if}

	{#if setup}
		<div class="flex flex-col gap-3 rounded-xl border border-line bg-raised p-4">
			<p class="text-sm">{t('totp.scan')}</p>
			<div class="w-fit rounded-lg bg-white p-2">
				<!-- vom Server erzeugtes SVG ohne Skripte und Inline-Styles -->
				{@html setup.qr_svg}
			</div>
			<p class="text-xs text-muted">
				{t('totp.secret')}:
				<code class="font-mono text-sm break-all text-fg" data-testid="totp-secret"
					>{setup.secret}</code
				>
			</p>
			<form class="flex flex-wrap items-end gap-2" onsubmit={confirm}>
				<div>
					<label class="label" for="{uid}-confirm">{t('totp.code')}</label>
					<input
						id="{uid}-confirm"
						class="input w-40 font-mono"
						inputmode="numeric"
						autocomplete="one-time-code"
						maxlength="6"
						required
						bind:value={code}
					/>
				</div>
				<button type="submit" class="btn btn-primary" disabled={busy}>{t('totp.confirm')}</button>
				<button type="button" class="btn btn-ghost" onclick={() => (setup = null)}>
					{t('task.cancel')}
				</button>
			</form>
		</div>
	{:else if status && !status.enabled}
		<p class="mb-3 text-sm text-muted">{t('totp.off')}</p>
		<form class="flex flex-wrap items-end gap-2" onsubmit={start}>
			<div>
				<label class="label" for="{uid}-password">{t('totp.password')}</label>
				<input
					id="{uid}-password"
					type="password"
					class="input"
					autocomplete="current-password"
					required
					bind:value={password}
				/>
			</div>
			<button type="submit" class="btn btn-primary" disabled={busy}>{t('totp.start')}</button>
		</form>
	{:else if status}
		<p class="mb-3 text-sm text-ok">
			{t('totp.on', {
				date: status.enabled_at ? formatDate(status.enabled_at) : '',
				count: status.recovery_codes_left
			})}
		</p>
		<div class="grid gap-4 sm:grid-cols-2">
			<form class="flex flex-col gap-2" onsubmit={regenerate}>
				<label class="label" for="{uid}-regen">{t('totp.password')}</label>
				<input
					id="{uid}-regen"
					type="password"
					class="input"
					autocomplete="current-password"
					required
					bind:value={password}
				/>
				<button type="submit" class="btn" disabled={busy}>{t('totp.newCodes')}</button>
			</form>
			<form class="flex flex-col gap-2" onsubmit={disable}>
				<label class="label" for="{uid}-disable-code">{t('totp.disableCode')}</label>
				<input
					id="{uid}-disable-code"
					class="input font-mono"
					autocomplete="one-time-code"
					maxlength="20"
					required
					bind:value={code}
				/>
				<button type="submit" class="btn btn-danger" disabled={busy || !password}>
					{t('totp.disable')}
				</button>
				<p class="text-xs text-muted">{t('totp.disableHint')}</p>
			</form>
		</div>
	{/if}
</section>
