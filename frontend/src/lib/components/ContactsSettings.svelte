<script lang="ts">
	import { Trash } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { t } from '$lib/i18n/index.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import type { Contact } from '$lib/types';

	let contacts = $state<Contact[]>([]);
	let filter = $state('');
	let confirmId = $state<string | null>(null);

	const shown = $derived.by(() => {
		const words = filter.toLowerCase().split(/\s+/).filter(Boolean);
		return contacts.filter((c) => {
			const text = [c.name, c.company, c.phone, c.email].join(' ').toLowerCase();
			return words.every((word) => text.includes(word));
		});
	});

	async function load() {
		try {
			contacts = await api<Contact[]>('/contacts', { query: { limit: 500 } });
		} catch (error) {
			toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
		}
	}

	onMount(load);

	async function remove(contact: Contact) {
		if (confirmId !== contact.id) {
			confirmId = contact.id;
			return;
		}
		try {
			await api(`/contacts/${contact.id}`, { method: 'DELETE' });
			toasts.show(t('contacts.deleted'));
			confirmId = null;
			await load();
		} catch (error) {
			toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
		}
	}
</script>

{#if contacts.length}
	<section aria-labelledby="contacts-title">
		<h2 id="contacts-title" class="mb-1 text-base font-semibold">{t('contacts.title')}</h2>
		<p class="mb-3 text-sm text-muted">{t('contacts.intro')}</p>
		{#if contacts.length > 5}
			<input
				type="search"
				class="input mb-3"
				aria-label={t('contacts.search')}
				placeholder={t('contacts.search')}
				bind:value={filter}
			/>
		{/if}
		{#if contacts.length}
			<ul class="flex flex-col divide-y divide-line rounded-xl border border-line bg-raised">
				{#each shown as contact (contact.id)}
					<li class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
						<div class="min-w-0">
							<p class="font-medium">{contact.name}</p>
							<p class="truncate text-xs text-muted">
								{[contact.company, contact.phone, contact.email].filter(Boolean).join(' · ')}
								{#if contact.use_count}
									· {t('contacts.used', { n: contact.use_count })}
								{/if}
							</p>
						</div>
						<button
							type="button"
							class="btn btn-ghost btn-danger"
							aria-label="{t('contacts.delete')}: {contact.name}"
							onclick={() => remove(contact)}
						>
							<Trash size={16} aria-hidden="true" />
							{confirmId === contact.id ? t('contacts.deleteConfirm') : t('contacts.delete')}
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}
