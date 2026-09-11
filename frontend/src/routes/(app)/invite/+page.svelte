<script lang="ts">
	import { Users } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { t, type MessageKey } from '$lib/i18n/index.svelte';
	import { areas } from '$lib/stores/areas.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';

	interface Preview {
		area_name: string;
		role: string;
		invited_by: string;
		already_member: boolean;
	}

	/** Einladungslink /invite#<geheimnis> – das Geheimnis geht nur im Body an den Server. */
	let token = $state('');
	let preview = $state<Preview | null>(null);
	let problem = $state('');
	let busy = $state(false);

	onMount(async () => {
		token = window.location.hash.slice(1);
		if (!token) {
			problem = t('invite.missing');
			return;
		}
		try {
			preview = await api<Preview>('/invites/preview', { method: 'POST', body: { token } });
		} catch (error) {
			problem = error instanceof ApiError ? error.message : t('error.generic');
		}
	});

	async function accept() {
		busy = true;
		try {
			await api('/invites/accept', { method: 'POST', body: { token } });
			await areas.refresh();
			toasts.show(t('invite.joined', { name: preview?.area_name ?? '' }));
			await goto('/areas', { replaceState: true });
		} catch (error) {
			toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
		} finally {
			busy = false;
		}
	}
</script>

<PageHeader title={t('invite.title')} />

{#if problem}
	<p class="text-sm text-danger" role="alert">{problem}</p>
{:else if preview}
	<div class="max-w-md rounded-xl border border-line bg-raised p-5">
		<p class="flex items-center gap-2 text-base font-medium">
			<Users size={18} aria-hidden="true" />{preview.area_name}
		</p>
		<p class="mt-1 text-sm text-muted">
			{t('invite.from', {
				name: preview.invited_by,
				role: t(`share.role.${preview.role}` as MessageKey)
			})}
		</p>
		{#if preview.already_member}
			<p class="mt-3 text-sm">{t('invite.already')}</p>
		{:else}
			<button type="button" class="btn btn-primary mt-4" disabled={busy} onclick={accept}>
				{t('invite.accept')}
			</button>
		{/if}
	</div>
{/if}
