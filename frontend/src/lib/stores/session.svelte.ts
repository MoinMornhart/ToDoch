import { api, ApiError, onUnauthorized } from '$lib/api';
import { i18n } from '$lib/i18n/index.svelte';
import type { Meta, User } from '$lib/types';

type Status = 'loading' | 'setup' | 'anonymous' | 'ready' | 'error';

function clearOfflineCache(): void {
	navigator.serviceWorker?.controller?.postMessage('clear-api-cache');
}

class Session {
	status = $state<Status>('loading');
	meta = $state<Meta | null>(null);
	user = $state<User | null>(null);

	async init(): Promise<void> {
		this.status = 'loading';
		try {
			this.meta = await api<Meta>('/meta');
			if (this.meta.setup_required) {
				this.status = 'setup';
				return;
			}
			this.setUser(await api<User>('/auth/me'));
		} catch (error) {
			if (error instanceof ApiError && error.status === 401) {
				this.status = 'anonymous';
			} else {
				this.status = 'error';
			}
		}
	}

	setUser(user: User): void {
		this.user = user;
		i18n.locale = user.locale;
		this.status = 'ready';
	}

	async login(email: string, password: string): Promise<void> {
		this.signedIn(await api<User>('/auth/login', { method: 'POST', body: { email, password } }));
	}

	/** Nach jeder Anmeldung (Passwort oder Passkey): alten Offline-Stand verwerfen. */
	signedIn(user: User): void {
		clearOfflineCache();
		this.setUser(user);
	}

	async logout(everywhere = false): Promise<void> {
		try {
			await api(everywhere ? '/auth/logout-all' : '/auth/logout', { method: 'POST' });
		} finally {
			this.signedOut();
		}
	}

	signedOut(): void {
		clearOfflineCache();
		this.user = null;
		if (this.status === 'ready') this.status = 'anonymous';
	}
}

export const session = new Session();

onUnauthorized(() => session.signedOut());
