<script lang="ts">
	import { Monitor, Moon, Sun } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { describeAgent } from '$lib/agent';
	import { api, ApiError } from '$lib/api';
	import ContactsSettings from '$lib/components/ContactsSettings.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import PushSettings from '$lib/components/PushSettings.svelte';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { theme, type ThemeMode } from '$lib/stores/theme.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';
	import type { Locale, SessionInfo, User } from '$lib/types';

	const themes = [
		{ mode: 'system', label: 'theme.system', icon: Monitor },
		{ mode: 'light', label: 'theme.light', icon: Sun },
		{ mode: 'dark', label: 'theme.dark', icon: Moon }
	] as const satisfies readonly { mode: ThemeMode; label: string; icon: typeof Sun }[];

	const initialZone = session.user?.timezone ?? 'Europe/Berlin';
	const zones = Array.from(new Set([initialZone, ...Intl.supportedValuesOf('timeZone')])).sort();

	let name = $state(session.user?.display_name ?? '');
	let timezone = $state(initialZone);
	let locale = $state<Locale>(session.user?.locale ?? 'de');
	let currentPassword = $state('');
	let newPassword = $state('');
	let sessions = $state<SessionInfo[]>([]);
	let busy = $state(false);

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	function formatDateTime(value: string): string {
		return new Intl.DateTimeFormat(i18n.locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
			new Date(value)
		);
	}

	async function loadSessions() {
		try {
			sessions = await api<SessionInfo[]>('/auth/sessions');
		} catch (error) {
			report(error);
		}
	}

	onMount(loadSessions);

	async function saveProfile(event: SubmitEvent) {
		event.preventDefault();
		try {
			const user = await api<User>('/auth/me', {
				method: 'PATCH',
				body: { display_name: name, timezone, locale }
			});
			session.setUser(user);
			toasts.show(t('settings.profileSaved'));
		} catch (error) {
			report(error);
		}
	}

	async function changePassword(event: SubmitEvent) {
		event.preventDefault();
		busy = true;
		try {
			await api('/auth/password', {
				method: 'POST',
				body: { current_password: currentPassword, new_password: newPassword }
			});
			currentPassword = '';
			newPassword = '';
			toasts.show(t('settings.passwordChanged'));
			await loadSessions();
		} catch (error) {
			report(error);
		} finally {
			busy = false;
		}
	}

	async function endSession(id: string) {
		try {
			await api(`/auth/sessions/${id}`, { method: 'DELETE' });
		} catch (error) {
			report(error);
		}
		await loadSessions();
	}

	async function logoutEverywhere() {
		await session.logout(true);
		await goto('/login', { replaceState: true });
	}
</script>

<PageHeader title={t('settings.title')} />

<div class="flex flex-col gap-10">
	<section aria-labelledby="profile-title">
		<h2 id="profile-title" class="mb-3 text-base font-semibold">{t('settings.profile')}</h2>
		<form class="grid gap-4 sm:grid-cols-2" onsubmit={saveProfile}>
			<div class="sm:col-span-2">
				<label class="label" for="display-name">{t('settings.name')}</label>
				<input id="display-name" class="input" maxlength="100" required bind:value={name} />
			</div>
			<div>
				<label class="label" for="timezone">{t('setup.timezone')}</label>
				<select id="timezone" class="input" bind:value={timezone}>
					{#each zones as zone (zone)}<option value={zone}>{zone}</option>{/each}
				</select>
			</div>
			<div>
				<label class="label" for="locale">{t('setup.language')}</label>
				<select id="locale" class="input" bind:value={locale}>
					<option value="de">Deutsch</option>
					<option value="en">English</option>
				</select>
			</div>
			<div class="sm:col-span-2">
				<button type="submit" class="btn btn-primary">{t('settings.saveProfile')}</button>
			</div>
		</form>
	</section>

	<section aria-labelledby="appearance-title">
		<h2 id="appearance-title" class="mb-3 text-base font-semibold">
			{t('settings.appearance')}
		</h2>
		<div
			role="group"
			aria-labelledby="appearance-title"
			class="inline-flex rounded-lg border border-line bg-raised p-1"
		>
			{#each themes as item (item.mode)}
				<button
					type="button"
					aria-pressed={theme.mode === item.mode}
					class="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm {theme.mode === item.mode
						? 'bg-surface-2 font-medium text-fg'
						: 'text-muted hover:text-fg'}"
					onclick={() => theme.set(item.mode)}
				>
					<item.icon size={16} aria-hidden="true" />{t(item.label)}
				</button>
			{/each}
		</div>
		<p class="mt-2 text-xs text-muted">{t('theme.hint')}</p>
	</section>

	<section aria-labelledby="password-title">
		<h2 id="password-title" class="mb-3 text-base font-semibold">{t('settings.password')}</h2>
		<form class="grid gap-4 sm:grid-cols-2" onsubmit={changePassword}>
			<input
				type="email"
				class="hidden"
				autocomplete="username"
				value={session.user?.email}
				readonly
			/>
			<div>
				<label class="label" for="current-password">{t('settings.currentPassword')}</label>
				<input
					id="current-password"
					type="password"
					class="input"
					autocomplete="current-password"
					required
					bind:value={currentPassword}
				/>
			</div>
			<div>
				<label class="label" for="new-password">{t('settings.newPassword')}</label>
				<input
					id="new-password"
					type="password"
					class="input"
					autocomplete="new-password"
					minlength="12"
					maxlength="256"
					required
					aria-describedby="new-password-hint"
					bind:value={newPassword}
				/>
				<p id="new-password-hint" class="mt-1 text-xs text-muted">{t('setup.passwordHint')}</p>
			</div>
			<div class="sm:col-span-2">
				<button type="submit" class="btn" disabled={busy}>{t('settings.changePassword')}</button>
			</div>
		</form>
	</section>

	<section aria-labelledby="sessions-title">
		<h2 id="sessions-title" class="mb-3 text-base font-semibold">{t('settings.sessions')}</h2>
		<ul class="flex flex-col divide-y divide-line rounded-xl border border-line bg-raised">
			{#each sessions as item (item.id)}
				<li class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
					<div>
						<p class="font-medium">
							{describeAgent(item.user_agent)}
							{#if item.current}
								<span class="ml-2 text-xs font-normal text-ok">{t('settings.thisDevice')}</span>
							{/if}
						</p>
						<p class="text-xs text-muted">
							{t('settings.lastSeen')}: {formatDateTime(item.last_seen_at)}{item.ip
								? ` · ${item.ip}`
								: ''}
						</p>
					</div>
					{#if !item.current}
						<button
							type="button"
							class="btn btn-ghost btn-danger"
							onclick={() => endSession(item.id)}
						>
							{t('settings.endSession')}
						</button>
					{/if}
				</li>
			{/each}
		</ul>
		<button type="button" class="btn btn-danger mt-3" onclick={logoutEverywhere}>
			{t('settings.logoutAll')}
		</button>
	</section>

	<ContactsSettings />

	<PushSettings />

	<section aria-labelledby="about-title">
		<h2 id="about-title" class="mb-1 text-base font-semibold">{t('settings.about')}</h2>
		<p class="text-sm text-muted">
			{t('settings.version', { version: session.meta?.version ?? '?' })}
		</p>
	</section>
</div>
