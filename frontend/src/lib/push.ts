/** Web-Push im Browser: Erinnerungen auf diesem Gerät aktivieren und deaktivieren. */

import { api } from '$lib/api';

export function urlBase64ToBytes(value: string): Uint8Array<ArrayBuffer> {
	const padded = value + '='.repeat((4 - (value.length % 4)) % 4);
	const raw = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
	const bytes = new Uint8Array(new ArrayBuffer(raw.length));
	for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
	return bytes;
}

export function pushSupported(): boolean {
	return (
		typeof window !== 'undefined' &&
		'serviceWorker' in navigator &&
		'PushManager' in window &&
		'Notification' in window
	);
}

export async function currentSubscription(): Promise<PushSubscription | null> {
	if (!pushSupported()) return null;
	const registration = await navigator.serviceWorker.getRegistration();
	return (await registration?.pushManager.getSubscription()) ?? null;
}

export type EnableResult = 'enabled' | 'denied' | 'unsupported';

export async function enablePush(): Promise<EnableResult> {
	if (!pushSupported()) return 'unsupported';
	const permission = await Notification.requestPermission();
	if (permission !== 'granted') return 'denied';
	const registration = await navigator.serviceWorker.ready;
	const { public_key } = await api<{ public_key: string }>('/push/key');
	const options = { userVisibleOnly: true, applicationServerKey: urlBase64ToBytes(public_key) };
	let subscription = await registration.pushManager.getSubscription();
	try {
		subscription ??= await registration.pushManager.subscribe(options);
	} catch {
		// Altes Abo mit anderem Serverschlüssel – erneuern.
		await subscription?.unsubscribe();
		subscription = await registration.pushManager.subscribe(options);
	}
	const json = subscription.toJSON();
	await api('/push/subscriptions', {
		method: 'POST',
		body: { endpoint: json.endpoint, keys: json.keys }
	});
	return 'enabled';
}

export async function disablePush(): Promise<void> {
	const subscription = await currentSubscription();
	if (!subscription) return;
	await api('/push/unsubscribe', {
		method: 'POST',
		body: { endpoint: subscription.endpoint }
	}).catch(() => undefined);
	await subscription.unsubscribe();
}
