<script lang="ts">
	import { ChevronDown, ChevronUp, Trash } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import AreaIcon from '$lib/components/AreaIcon.svelte';
	import CalendarFeeds from '$lib/components/CalendarFeeds.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import { AREA_ICONS } from '$lib/labels';
	import { areas } from '$lib/stores/areas.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import { ui } from '$lib/stores/ui.svelte';
	import type { Area } from '$lib/types';

	let name = $state('');
	let color = $state('#6b7280');
	let icon = $state<string>('circle');
	let deleting = $state<string | null>(null);
	let moveTo = $state('');

	onMount(() => {
		void areas.refresh();
	});

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	async function create(event: SubmitEvent) {
		event.preventDefault();
		if (!name.trim()) return;
		try {
			const order = (areas.list.at(-1)?.sort_order ?? 0) + 1;
			await api('/areas', {
				method: 'POST',
				body: { name: name.trim(), color, icon, sort_order: order }
			});
			name = '';
			await areas.refresh();
		} catch (error) {
			report(error);
		}
	}

	async function update(area: Area, patch: Partial<Pick<Area, 'name' | 'color' | 'icon'>>) {
		try {
			await api(`/areas/${area.id}`, { method: 'PATCH', body: patch });
			ui.changed();
		} catch (error) {
			report(error);
		}
		await areas.refresh();
	}

	async function move(index: number, delta: number) {
		const list = [...areas.list];
		const [area] = list.splice(index, 1);
		if (!area) return;
		list.splice(index + delta, 0, area);
		try {
			await Promise.all(
				list.map((item, order) =>
					item.sort_order === order
						? null
						: api(`/areas/${item.id}`, { method: 'PATCH', body: { sort_order: order } })
				)
			);
		} catch (error) {
			report(error);
		}
		await areas.refresh();
	}

	function startDelete(area: Area) {
		deleting = area.id;
		moveTo = areas.list.find((other) => other.id !== area.id)?.id ?? '';
	}

	async function remove(area: Area) {
		try {
			await api(`/areas/${area.id}`, {
				method: 'DELETE',
				query: { move_to: moveTo || undefined }
			});
			deleting = null;
			ui.changed();
		} catch (error) {
			report(error);
		}
		await areas.refresh();
	}
</script>

<PageHeader title={t('areas.title')} />

<ul class="flex flex-col divide-y divide-line rounded-xl border border-line bg-raised">
	{#each areas.list as area, index (area.id)}
		<li class="flex flex-wrap items-center gap-2 px-3 py-2.5">
			<input
				type="color"
				value={area.color}
				aria-label="{t('areas.color')}: {area.name}"
				onchange={(event) => update(area, { color: event.currentTarget.value })}
				class="size-8 shrink-0 cursor-pointer rounded border border-line bg-transparent"
			/>
			<AreaIcon name={area.icon} size={16} class="shrink-0 text-muted" />
			<select
				value={area.icon}
				aria-label="{t('areas.icon')}: {area.name}"
				onchange={(event) => update(area, { icon: event.currentTarget.value })}
				class="input w-auto py-1 text-sm"
			>
				{#each AREA_ICONS as option (option)}<option value={option}>{option}</option>{/each}
			</select>
			<input
				class="input min-w-32 flex-1 py-1"
				value={area.name}
				aria-label="{t('areas.name')}: {area.name}"
				maxlength="60"
				onchange={(event) => {
					const value = event.currentTarget.value.trim();
					if (value && value !== area.name) void update(area, { name: value });
				}}
			/>
			<span class="text-xs text-muted">{t('areas.open', { count: area.open_count })}</span>
			<div class="flex">
				<button
					type="button"
					class="icon-btn"
					aria-label="{t('areas.up')}: {area.name}"
					disabled={index === 0}
					onclick={() => move(index, -1)}
				>
					<ChevronUp size={16} aria-hidden="true" />
				</button>
				<button
					type="button"
					class="icon-btn"
					aria-label="{t('areas.down')}: {area.name}"
					disabled={index === areas.list.length - 1}
					onclick={() => move(index, 1)}
				>
					<ChevronDown size={16} aria-hidden="true" />
				</button>
				<button
					type="button"
					class="icon-btn hover:text-danger"
					aria-label="{t('areas.delete')}: {area.name}"
					disabled={areas.list.length < 2}
					onclick={() => startDelete(area)}
				>
					<Trash size={16} aria-hidden="true" />
				</button>
			</div>
			{#if deleting === area.id}
				<div class="flex w-full flex-wrap items-center gap-2 pt-1 text-sm">
					<label class="flex items-center gap-2">
						{t('areas.moveTo')}
						<select class="input w-auto py-1" bind:value={moveTo}>
							{#each areas.list.filter((other) => other.id !== area.id) as other (other.id)}
								<option value={other.id}>{other.name}</option>
							{/each}
						</select>
					</label>
					<button type="button" class="btn btn-danger" onclick={() => remove(area)}>
						{t('task.deleteConfirm')}
					</button>
					<button type="button" class="btn" onclick={() => (deleting = null)}>
						{t('task.cancel')}
					</button>
				</div>
			{/if}
		</li>
	{/each}
</ul>

<form class="mt-8" onsubmit={create}>
	<h2 class="mb-3 text-base font-semibold">{t('areas.new')}</h2>
	<div class="flex flex-wrap items-end gap-2">
		<div class="min-w-40 flex-1">
			<label class="label" for="area-name">{t('areas.name')}</label>
			<input id="area-name" class="input" maxlength="60" required bind:value={name} />
		</div>
		<div>
			<label class="label" for="area-color">{t('areas.color')}</label>
			<input
				id="area-color"
				type="color"
				class="h-10 w-12 cursor-pointer rounded border border-line bg-transparent"
				bind:value={color}
			/>
		</div>
		<div>
			<label class="label" for="area-icon">{t('areas.icon')}</label>
			<select id="area-icon" class="input w-auto" bind:value={icon}>
				{#each AREA_ICONS as option (option)}<option value={option}>{option}</option>{/each}
			</select>
		</div>
		<button type="submit" class="btn btn-primary">{t('areas.add')}</button>
	</div>
</form>

<CalendarFeeds />
