<script lang="ts">
	import { Bell, BellOff, Trash } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { describeAgent } from '$lib/agent';
	import { api, ApiError } from '$lib/api';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { currentSubscription, disablePush, enablePush, pushSupported } from '$lib/push';
	import { toasts } from '$lib/stores/toasts.svelte';
	import type { PushDevice } from '$lib/types';

	const uid = $props.id();
	let supported = $state(true);
	let denied = $state(false);
	let active = $state(false);
	let busy = $state(false);
	let devices = $state<PushDevice[]>([]);
	let iosHint = $state(false);

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	async function refresh() {
		supported = pushSupported();
		denied = supported && Notification.permission === 'denied';
		active = supported && (await currentSubscription()) !== null;
		try {
			devices = await api<PushDevice[]>('/push/subscriptions');
		} catch (error) {
			report(error);
		}
	}

	onMount(() => {
		const standalone = matchMedia('(display-mode: standalone)').matches;
		iosHint = /iPhone|iPad/.test(navigator.userAgent) && !standalone;
		void refresh();
	});

	async function enable() {
		busy = true;
		try {
			const result = await enablePush();
			if (result === 'denied') denied = true;
		} catch (error) {
			report(error);
		} finally {
			busy = false;
			await refresh();
		}
	}

	async function disable() {
		busy = true;
		try {
			await disablePush();
		} finally {
			busy = false;
			await refresh();
		}
	}

	async function sendTest() {
		try {
			await api('/push/test', { method: 'POST' });
			toasts.show(t('push.testSent'));
		} catch (error) {
			report(error);
		}
	}

	async function remove(device: PushDevice) {
		try {
			await api(`/push/subscriptions/${device.id}`, { method: 'DELETE' });
		} catch (error) {
			report(error);
		}
		await refresh();
	}

	function formatDate(value: string): string {
		return new Intl.DateTimeFormat(i18n.locale, { dateStyle: 'medium' }).format(new Date(value));
	}
</script>

<section aria-labelledby="{uid}-title">
	<h2 id="{uid}-title" class="mb-1 text-base font-semibold">{t('push.title')}</h2>
	<p class="mb-3 text-sm text-muted">{t('push.intro')}</p>

	{#if !supported}
		<p class="text-sm text-warn">{t('push.unsupported')}</p>
	{:else}
		{#if iosHint}<p class="mb-3 text-sm text-warn">{t('push.iosHint')}</p>{/if}
		{#if denied}<p class="mb-3 text-sm text-danger">{t('push.denied')}</p>{/if}
		<p class="mb-3 flex items-center gap-2 text-sm">
			{#if active}
				<Bell size={16} class="text-ok" aria-hidden="true" />{t('push.enabled')}
			{:else}
				<BellOff size={16} class="text-muted" aria-hidden="true" />{t('push.disabledState')}
			{/if}
		</p>
		<div class="flex flex-wrap gap-2">
			{#if active}
				<button type="button" class="btn" onclick={sendTest}>{t('push.test')}</button>
				<button type="button" class="btn btn-ghost" disabled={busy} onclick={disable}>
					{t('push.disable')}
				</button>
			{:else}
				<button type="button" class="btn btn-primary" disabled={busy || denied} onclick={enable}>
					<Bell size={16} aria-hidden="true" />{t('push.enable')}
				</button>
			{/if}
		</div>
	{/if}

	{#if devices.length}
		<h3 class="mt-5 mb-2 text-sm font-medium">{t('push.devices')}</h3>
		<ul class="flex flex-col divide-y divide-line rounded-xl border border-line bg-raised">
			{#each devices as device (device.id)}
				<li class="flex items-center justify-between gap-2 px-4 py-2.5 text-sm">
					<span>
						{describeAgent(device.user_agent)}
						<span class="text-xs text-muted">· {formatDate(device.created_at)}</span>
					</span>
					<button
						type="button"
						class="icon-btn hover:text-danger"
						aria-label="{t('push.remove')}: {describeAgent(device.user_agent)}"
						onclick={() => remove(device)}
					>
						<Trash size={16} aria-hidden="true" />
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</section>
