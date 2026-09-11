<script lang="ts">
	import { Copy, Link, Trash, UserMinus } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { t, type MessageKey } from '$lib/i18n/index.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import type { Area } from '$lib/types';

	interface Member {
		id: string | null;
		display_name: string;
		role: string;
		you: boolean;
	}

	interface Invite {
		id: string;
		role: string;
		created_at: string;
		expires_at: string;
	}

	/** Mitglieder und Einladungslinks eines Bereichs – nur für Besitzer und Admins. */
	let { area }: { area: Area } = $props();
	const uid = $props.id();
	const ROLES = ['member', 'viewer', 'admin'] as const;

	let members = $state<Member[]>([]);
	let invites = $state<Invite[]>([]);
	let role = $state<(typeof ROLES)[number]>('member');
	let link = $state('');

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	function roleName(value: string): string {
		return t(`share.role.${value}` as MessageKey);
	}

	async function load() {
		try {
			[members, invites] = await Promise.all([
				api<Member[]>(`/areas/${area.id}/members`),
				api<Invite[]>(`/areas/${area.id}/invites`)
			]);
		} catch (error) {
			report(error);
		}
	}

	onMount(load);

	async function invite() {
		try {
			const created = await api<{ url: string }>(`/areas/${area.id}/invites`, {
				method: 'POST',
				body: { role }
			});
			link = created.url;
			await load();
		} catch (error) {
			report(error);
		}
	}

	async function copy() {
		try {
			await navigator.clipboard.writeText(link);
			toasts.show(t('share.copied'));
		} catch {
			// Zwischenablage gesperrt – der Link steht im Feld zum Markieren
		}
	}

	async function changeRole(member: Member, value: string) {
		if (!member.id) return;
		try {
			await api(`/areas/${area.id}/members/${member.id}`, {
				method: 'PATCH',
				body: { role: value }
			});
			await load();
		} catch (error) {
			report(error);
		}
	}

	async function removeMember(member: Member) {
		if (!member.id) return;
		try {
			await api(`/areas/${area.id}/members/${member.id}`, { method: 'DELETE' });
			await load();
		} catch (error) {
			report(error);
		}
	}

	async function revoke(item: Invite) {
		try {
			await api(`/areas/${area.id}/invites/${item.id}`, { method: 'DELETE' });
			await load();
		} catch (error) {
			report(error);
		}
	}
</script>

<div
	class="w-full rounded-lg bg-surface-2 p-3 text-sm"
	aria-label={t('share.title', { name: area.name })}
>
	<ul class="mb-3 flex flex-col gap-1">
		{#each members as member (member.id ?? 'owner')}
			<li class="flex flex-wrap items-center gap-2">
				<span class="min-w-0 flex-1 truncate">
					{member.display_name}
					{#if member.you}<span class="text-muted">({t('share.you')})</span>{/if}
				</span>
				{#if member.id && !member.you}
					<select
						class="input w-auto py-1 text-xs"
						aria-label="{t('share.roleOf')}: {member.display_name}"
						value={member.role}
						onchange={(event) => changeRole(member, event.currentTarget.value)}
					>
						{#each ROLES as option (option)}
							<option value={option}>{roleName(option)}</option>
						{/each}
					</select>
					<button
						type="button"
						class="icon-btn hover:text-danger"
						aria-label="{t('share.remove')}: {member.display_name}"
						onclick={() => removeMember(member)}
					>
						<UserMinus size={14} aria-hidden="true" />
					</button>
				{:else}
					<span class="text-xs text-muted">{roleName(member.role)}</span>
				{/if}
			</li>
		{/each}
	</ul>

	<div class="flex flex-wrap items-end gap-2">
		<div>
			<label class="label" for="{uid}-role">{t('share.inviteAs')}</label>
			<select id="{uid}-role" class="input w-auto py-1" bind:value={role}>
				{#each ROLES as option (option)}
					<option value={option}>{roleName(option)}</option>
				{/each}
			</select>
		</div>
		<button type="button" class="btn btn-primary" onclick={invite}>
			<Link size={14} aria-hidden="true" />{t('share.createLink')}
		</button>
	</div>
	{#if link}
		<div class="mt-2 flex flex-wrap items-center gap-2">
			<input
				class="input min-w-0 flex-1 font-mono text-xs"
				readonly
				value={link}
				aria-label={t('share.link')}
				onfocus={(event) => event.currentTarget.select()}
			/>
			<button type="button" class="btn btn-ghost" onclick={copy}>
				<Copy size={14} aria-hidden="true" />{t('share.copy')}
			</button>
		</div>
		<p class="mt-1 text-xs text-muted">{t('share.linkHint')}</p>
	{/if}
	{#if invites.length}
		<p class="mt-3 text-xs text-muted">{t('share.open', { count: invites.length })}</p>
		<ul class="mt-1 flex flex-col gap-1 text-xs">
			{#each invites as item (item.id)}
				<li class="flex items-center gap-2">
					<span class="flex-1">
						{roleName(item.role)} · {t('share.until', {
							date: new Date(item.expires_at).toLocaleDateString()
						})}
					</span>
					<button
						type="button"
						class="icon-btn hover:text-danger"
						aria-label={t('share.revoke')}
						onclick={() => revoke(item)}
					>
						<Trash size={12} aria-hidden="true" />
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>
