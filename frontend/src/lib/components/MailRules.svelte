<script lang="ts">
	import { Filter, Play, Plus, Trash } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { t } from '$lib/i18n/index.svelte';
	import type { MailAccountInfo, MailRuleInfo } from '$lib/mail';
	import { areas } from '$lib/stores/areas.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import { ui } from '$lib/stores/ui.svelte';

	let {
		accounts,
		onchange
	}: { accounts: MailAccountInfo[]; onchange?: () => void | Promise<void> } = $props();
	const uid = $props.id();
	const priorities = [
		{ value: 0, label: t('priority.0') },
		{ value: 1, label: t('priority.1') },
		{ value: 2, label: t('priority.2') },
		{ value: 3, label: t('priority.3') }
	];

	let rules = $state<MailRuleInfo[]>([]);
	let name = $state('');
	let accountId = $state('');
	let fromContains = $state('');
	let subjectContains = $state('');
	let bodyContains = $state('');
	let createTask = $state(true);
	let markRead = $state(false);
	let areaId = $state('');
	let priority = $state(0);
	let busy = $state(false);
	let confirmId = $state<string | null>(null);

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	async function load() {
		try {
			rules = await api<MailRuleInfo[]>('/mail/rules');
		} catch (error) {
			report(error);
		}
	}

	onMount(load);

	function summary(rule: MailRuleInfo): string {
		const conditions: string[] = [];
		if (rule.from_contains) conditions.push(t('rules.fromIs', { text: rule.from_contains }));
		if (rule.subject_contains)
			conditions.push(t('rules.subjectIs', { text: rule.subject_contains }));
		if (rule.body_contains) conditions.push(t('rules.bodyIs', { text: rule.body_contains }));
		const actions: string[] = [];
		if (rule.create_task)
			actions.push(t('rules.actionTask', { area: rule.area_name ?? areas.list[0]?.name ?? '' }));
		if (rule.mark_read) actions.push(t('rules.actionRead'));
		return `${conditions.join(` ${t('rules.and')} `)} → ${actions.join(', ')}`;
	}

	async function add(event: SubmitEvent) {
		event.preventDefault();
		if (busy) return;
		busy = true;
		try {
			await api('/mail/rules', {
				method: 'POST',
				body: {
					name: name.trim(),
					account_id: accountId || null,
					from_contains: fromContains.trim(),
					subject_contains: subjectContains.trim(),
					body_contains: bodyContains.trim(),
					create_task: createTask,
					mark_read: markRead,
					area_id: areaId || null,
					priority
				}
			});
			name = '';
			fromContains = '';
			subjectContains = '';
			bodyContains = '';
			toasts.show(t('rules.added'));
			await load();
		} catch (error) {
			report(error);
		} finally {
			busy = false;
		}
	}

	async function toggle(rule: MailRuleInfo) {
		try {
			await api(`/mail/rules/${rule.id}`, { method: 'PATCH', body: { enabled: !rule.enabled } });
			await load();
		} catch (error) {
			report(error);
		}
	}

	async function applyNow(rule: MailRuleInfo) {
		try {
			const result = await api<{ matched: number }>(`/mail/rules/${rule.id}/apply`, {
				method: 'POST'
			});
			toasts.show(t('rules.applied', { count: result.matched }));
			ui.changed();
			await load();
			await onchange?.();
		} catch (error) {
			report(error);
		}
	}

	async function remove(rule: MailRuleInfo) {
		if (confirmId !== rule.id) {
			confirmId = rule.id;
			return;
		}
		try {
			await api(`/mail/rules/${rule.id}`, { method: 'DELETE' });
			confirmId = null;
			toasts.show(t('rules.removed'));
			await load();
		} catch (error) {
			report(error);
		}
	}
</script>

<section aria-labelledby="{uid}-title">
	<h2 id="{uid}-title" class="mb-1 flex items-center gap-2 text-base font-semibold">
		<Filter size={16} aria-hidden="true" />{t('rules.title')}
	</h2>
	<p class="mb-3 text-sm text-muted">{t('rules.intro')}</p>

	{#if rules.length}
		<ul class="mb-4 flex flex-col divide-y divide-line rounded-xl border border-line bg-raised">
			{#each rules as rule (rule.id)}
				<li class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
					<div class="min-w-0">
						<label class="flex items-center gap-2 font-medium">
							<input type="checkbox" checked={rule.enabled} onchange={() => toggle(rule)} />
							{rule.name}
						</label>
						<p class="text-xs text-muted">
							{summary(rule)}
							{#if rule.account_name}· {rule.account_name}{/if}
							· {t('rules.matches', { count: rule.match_count })}
						</p>
					</div>
					<div class="flex flex-wrap gap-1">
						<button type="button" class="btn btn-ghost" onclick={() => applyNow(rule)}>
							<Play size={14} aria-hidden="true" />{t('rules.applyNow')}
						</button>
						<button
							type="button"
							class="btn btn-ghost btn-danger"
							aria-label="{t('rules.remove')}: {rule.name}"
							onclick={() => remove(rule)}
						>
							<Trash size={14} aria-hidden="true" />
							{confirmId === rule.id ? t('rules.removeConfirm') : t('rules.remove')}
						</button>
					</div>
				</li>
			{/each}
		</ul>
	{:else}
		<p class="mb-4 text-sm text-muted">{t('rules.none')}</p>
	{/if}

	<form class="grid gap-3 sm:grid-cols-2" onsubmit={add}>
		<div>
			<label class="label" for="{uid}-name">{t('rules.name')}</label>
			<input
				id="{uid}-name"
				class="input"
				required
				maxlength="100"
				placeholder={t('rules.namePlaceholder')}
				bind:value={name}
			/>
		</div>
		<div>
			<label class="label" for="{uid}-account">{t('rules.account')}</label>
			<select id="{uid}-account" class="input" bind:value={accountId}>
				<option value="">{t('mail.allAccounts')}</option>
				{#each accounts as account (account.id)}
					<option value={account.id}>{account.name}</option>
				{/each}
			</select>
		</div>
		<div>
			<label class="label" for="{uid}-from">{t('rules.from')}</label>
			<input
				id="{uid}-from"
				class="input"
				maxlength="200"
				placeholder="rechnung@"
				bind:value={fromContains}
			/>
		</div>
		<div>
			<label class="label" for="{uid}-subject">{t('rules.subject')}</label>
			<input id="{uid}-subject" class="input" maxlength="200" bind:value={subjectContains} />
		</div>
		<div class="sm:col-span-2">
			<label class="label" for="{uid}-body">{t('rules.body')}</label>
			<input id="{uid}-body" class="input" maxlength="200" bind:value={bodyContains} />
		</div>
		<fieldset class="grid gap-3 sm:col-span-2 sm:grid-cols-3">
			<legend class="label">{t('rules.actions')}</legend>
			<label class="flex items-center gap-2 text-sm">
				<input type="checkbox" bind:checked={createTask} />{t('rules.createTask')}
			</label>
			<div>
				<label class="label" for="{uid}-area">{t('rules.area')}</label>
				<select id="{uid}-area" class="input" disabled={!createTask} bind:value={areaId}>
					<option value="">{areas.list[0]?.name ?? ''}</option>
					{#each areas.list.slice(1) as area (area.id)}
						<option value={area.id}>{area.name}</option>
					{/each}
				</select>
			</div>
			<div>
				<label class="label" for="{uid}-priority">{t('rules.priority')}</label>
				<select id="{uid}-priority" class="input" disabled={!createTask} bind:value={priority}>
					{#each priorities as option (option.value)}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
			</div>
			<label class="flex items-center gap-2 text-sm">
				<input type="checkbox" bind:checked={markRead} />{t('rules.markRead')}
			</label>
		</fieldset>
		<div>
			<button type="submit" class="btn btn-primary" disabled={busy}>
				<Plus size={16} aria-hidden="true" />{t('rules.add')}
			</button>
		</div>
	</form>
</section>
