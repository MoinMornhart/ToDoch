<script lang="ts">
	import {
		CalendarDays,
		CalendarRange,
		CircleCheckBig,
		Keyboard,
		Layers,
		ListTodo,
		LogOut,
		Search,
		Settings,
		Sun
	} from '@lucide/svelte';
	import { onMount, type Snippet } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import AreaSwitcher from '$lib/components/AreaSwitcher.svelte';
	import ChoiceDialog from '$lib/components/ChoiceDialog.svelte';
	import EventEditor from '$lib/components/EventEditor.svelte';
	import { todayIn } from '$lib/dates';
	import HelpDialog from '$lib/components/HelpDialog.svelte';
	import Logo from '$lib/components/Logo.svelte';
	import SearchDialog from '$lib/components/SearchDialog.svelte';
	import TaskEditor from '$lib/components/TaskEditor.svelte';
	import { t, type MessageKey } from '$lib/i18n/index.svelte';
	import { plainKey } from '$lib/keyboard';
	import { areas } from '$lib/stores/areas.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { ui } from '$lib/stores/ui.svelte';

	let { children }: { children: Snippet } = $props();

	const primary: { href: string; label: MessageKey; icon: typeof Sun }[] = [
		{ href: '/today', label: 'nav.today', icon: Sun },
		{ href: '/upcoming', label: 'nav.upcoming', icon: CalendarDays },
		{ href: '/open', label: 'nav.open', icon: ListTodo },
		{ href: '/done', label: 'nav.done', icon: CircleCheckBig }
	];
	const secondary: typeof primary = [
		{ href: '/calendar', label: 'nav.calendar', icon: CalendarRange },
		{ href: '/areas', label: 'nav.areas', icon: Layers },
		{ href: '/settings', label: 'nav.settings', icon: Settings }
	];
	// Handy: Heute, Demnächst, Alle offen, Kalender, Einstellungen
	const tabs = [...primary.slice(0, 3), secondary[0]!, secondary[2]!];

	const isActive = (href: string) => page.url.pathname === href;

	onMount(() => {
		void areas.refresh().catch(() => undefined);
	});

	function onKeydown(event: KeyboardEvent) {
		if (ui.dialogOpen) return;
		const key = plainKey(event);
		if (key === 'n') {
			event.preventDefault();
			ui.quickAddPending = true;
			if (!ui.quickAddMounted) void goto('/today');
		} else if (key === 'c') {
			event.preventDefault();
			ui.eventEditor = { mode: 'new', date: todayIn(session.user?.timezone ?? 'UTC') };
		} else if (key === '/') {
			event.preventDefault();
			ui.searchOpen = true;
		} else if (key === '?') {
			event.preventDefault();
			ui.helpOpen = true;
		}
	}

	async function logout() {
		await session.logout();
		await goto('/login', { replaceState: true });
	}
</script>

<svelte:window onkeydown={onKeydown} />

<div class="mx-auto flex min-h-dvh max-w-6xl">
	<nav
		aria-label={t('nav.main')}
		class="sticky top-0 hidden h-dvh w-56 shrink-0 flex-col gap-0.5 border-r border-line px-3 py-5 md:flex"
	>
		<a
			href="/today"
			class="mb-5 flex items-center gap-2.5 px-2 text-lg font-semibold tracking-tight"
		>
			<Logo size={26} />
			Todoch
		</a>
		{#each primary as item (item.href)}
			<a
				href={item.href}
				aria-current={isActive(item.href) ? 'page' : undefined}
				class="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm {isActive(item.href)
					? 'bg-surface-2 font-medium text-fg'
					: 'text-muted hover:text-fg'}"
			>
				<item.icon size={17} aria-hidden="true" />
				{t(item.label)}
			</a>
		{/each}
		<div class="my-3 border-t border-line"></div>
		{#each secondary as item (item.href)}
			<a
				href={item.href}
				aria-current={isActive(item.href) ? 'page' : undefined}
				class="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm {isActive(item.href)
					? 'bg-surface-2 font-medium text-fg'
					: 'text-muted hover:text-fg'}"
			>
				<item.icon size={17} aria-hidden="true" />
				{t(item.label)}
			</a>
		{/each}
		<div class="mt-auto flex items-center justify-between gap-2 px-2 text-sm">
			<span class="truncate text-muted">{session.user?.display_name}</span>
			<button type="button" class="icon-btn" aria-label={t('nav.logout')} onclick={logout}>
				<LogOut size={16} aria-hidden="true" />
			</button>
		</div>
	</nav>

	<div class="flex min-w-0 flex-1 flex-col">
		<header
			class="sticky top-0 z-10 flex items-center gap-2 border-b border-line bg-surface/90 px-4 py-2 backdrop-blur md:px-8"
		>
			<AreaSwitcher />
			<span class="flex-1"></span>
			<button
				type="button"
				class="icon-btn"
				aria-label={t('nav.search')}
				onclick={() => (ui.searchOpen = true)}
			>
				<Search size={18} aria-hidden="true" />
			</button>
			<button
				type="button"
				class="icon-btn hidden md:inline-grid"
				aria-label={t('nav.help')}
				onclick={() => (ui.helpOpen = true)}
			>
				<Keyboard size={18} aria-hidden="true" />
			</button>
		</header>
		<main
			id="main"
			class="w-full flex-1 px-4 pt-5 pb-28 md:px-8 md:pb-12 {page.url.pathname === '/calendar'
				? ''
				: 'max-w-3xl'}"
		>
			{@render children()}
		</main>
	</div>
</div>

<nav
	aria-label={t('nav.main')}
	class="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
>
	{#each tabs as item (item.href)}
		<a
			href={item.href}
			aria-current={isActive(item.href) ? 'page' : undefined}
			class="flex flex-col items-center gap-0.5 py-2 text-[11px] {isActive(item.href)
				? 'text-accent'
				: 'text-muted'}"
		>
			<item.icon size={20} aria-hidden="true" />
			{t(item.label)}
		</a>
	{/each}
</nav>

<SearchDialog />
<HelpDialog />
<TaskEditor />
<EventEditor />
<ChoiceDialog />
