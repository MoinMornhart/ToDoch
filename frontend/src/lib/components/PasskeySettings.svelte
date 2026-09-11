<script lang="ts">
	import { Cloud, KeyRound, Pencil, Trash } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { describeAgent } from '$lib/agent';
	import { api, ApiError } from '$lib/api';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { addPasskey } from '$lib/passkeys';
	import { toasts } from '$lib/stores/toasts.svelte';
	import type { PasskeyInfo } from '$lib/types';
	import { isCancelled, passkeysSupported } from '$lib/webauthn';

	let passkeys = $state<PasskeyInfo[]>([]);
	let supported = $state(false);
	let name = $state('');
	let password = $state('');
	let busy = $state(false);
	let confirmId = $state<string | null>(null);
	let editId = $state<string | null>(null);
	let editName = $state('');

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	function formatDate(value: string): string {
		return new Intl.DateTimeFormat(i18n.locale, { dateStyle: 'medium' }).format(new Date(value));
	}

	async function load() {
		try {
			passkeys = await api<PasskeyInfo[]>('/auth/passkeys');
		} catch (error) {
			report(error);
		}
	}

	onMount(() => {
		supported = passkeysSupported();
		name = describeAgent(navigator.userAgent);
		void load();
	});

	async function add(event: SubmitEvent) {
		event.preventDefault();
		busy = true;
		try {
			await addPasskey(password, name.trim() || describeAgent(navigator.userAgent));
			password = '';
			toasts.show(t('passkeys.added'));
			await load();
		} catch (error) {
			if (error instanceof DOMException && error.name === 'InvalidStateError') {
				toasts.error(t('passkeys.exists'));
			} else if (isCancelled(error)) {
				toasts.error(t('passkeys.cancelled'));
			} else {
				report(error);
			}
		} finally {
			busy = false;
		}
	}

	async function rename(passkey: PasskeyInfo) {
		const value = editName.trim();
		if (!value || value === passkey.name) {
			editId = null;
			return;
		}
		try {
			await api(`/auth/passkeys/${passkey.id}`, { method: 'PATCH', body: { name: value } });
			toasts.show(t('passkeys.renamed'));
			editId = null;
			await load();
		} catch (error) {
			report(error);
		}
	}

	async function remove(passkey: PasskeyInfo) {
		if (confirmId !== passkey.id) {
			confirmId = passkey.id;
			return;
		}
		try {
			await api(`/auth/passkeys/${passkey.id}`, { method: 'DELETE' });
			toasts.show(t('passkeys.deleted'));
			confirmId = null;
			await load();
		} catch (error) {
			report(error);
		}
	}
</script>

<section aria-labelledby="passkeys-title">
	<h2 id="passkeys-title" class="mb-1 flex items-center gap-2 text-base font-semibold">
		<KeyRound size={18} aria-hidden="true" />{t('passkeys.title')}
	</h2>
	<p class="mb-3 text-sm text-muted">{t('passkeys.intro')}</p>

	{#if passkeys.length}
		<ul class="mb-4 flex flex-col divide-y divide-line rounded-xl border border-line bg-raised">
			{#each passkeys as passkey (passkey.id)}
				<li class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
					{#if editId === passkey.id}
						<form
							class="flex flex-1 gap-2"
							onsubmit={(event) => {
								event.preventDefault();
								void rename(passkey);
							}}
						>
							<input
								class="input"
								aria-label={t('passkeys.name')}
								maxlength="100"
								bind:value={editName}
							/>
							<button type="submit" class="btn">{t('passkeys.saveName')}</button>
						</form>
					{:else}
						<div class="min-w-0">
							<p class="flex items-center gap-2 font-medium">
								{passkey.name}
								{#if passkey.backed_up}
									<span class="inline-flex items-center gap-1 text-xs font-normal text-muted">
										<Cloud size={12} aria-hidden="true" />{t('passkeys.synced')}
									</span>
								{/if}
							</p>
							<p class="text-xs text-muted">
								{t('passkeys.created', { date: formatDate(passkey.created_at) })} ·
								{passkey.last_used_at
									? t('passkeys.lastUsed', { date: formatDate(passkey.last_used_at) })
									: t('passkeys.neverUsed')}
							</p>
						</div>
						<div class="flex gap-1">
							<button
								type="button"
								class="icon-btn"
								aria-label="{t('passkeys.rename')}: {passkey.name}"
								onclick={() => {
									editId = passkey.id;
									editName = passkey.name;
								}}
							>
								<Pencil size={16} aria-hidden="true" />
							</button>
							<button
								type="button"
								class="btn btn-ghost btn-danger"
								aria-label="{t('passkeys.delete')}: {passkey.name}"
								onclick={() => remove(passkey)}
							>
								<Trash size={16} aria-hidden="true" />
								{confirmId === passkey.id ? t('passkeys.deleteConfirm') : t('passkeys.delete')}
							</button>
						</div>
					{/if}
				</li>
			{/each}
		</ul>
	{:else}
		<p class="mb-4 text-sm text-muted">{t('passkeys.none')}</p>
	{/if}

	{#if supported}
		<form class="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end" onsubmit={add}>
			<div>
				<label class="label" for="passkey-name">{t('passkeys.name')}</label>
				<input
					id="passkey-name"
					class="input"
					maxlength="100"
					placeholder={t('passkeys.namePlaceholder')}
					bind:value={name}
				/>
			</div>
			<div>
				<label class="label" for="passkey-password">{t('passkeys.password')}</label>
				<input
					id="passkey-password"
					type="password"
					class="input"
					autocomplete="current-password"
					required
					bind:value={password}
				/>
			</div>
			<button type="submit" class="btn btn-primary" disabled={busy}>
				<KeyRound size={16} aria-hidden="true" />{t('passkeys.add')}
			</button>
		</form>
	{:else}
		<p class="text-sm text-muted">{t('passkeys.unsupported')}</p>
	{/if}
</section>
