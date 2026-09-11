/** Abläufe rund um Passkeys: anmelden und neuen Passkey hinzufügen. */

import { api } from '$lib/api';
import type { PasskeyInfo, User } from '$lib/types';
import {
	credentialToJSON,
	toCreationOptions,
	toRequestOptions,
	type CreationOptionsJSON,
	type RequestOptionsJSON
} from '$lib/webauthn';

/**
 * Anmelden mit Passkey. ``conditional`` = still im Autofill des E-Mail-Felds anbieten;
 * gibt ``null`` zurück, wenn nichts ausgewählt wurde.
 */
export async function signInWithPasskey(
	options: { signal?: AbortSignal; conditional?: boolean } = {}
): Promise<User | null> {
	const { challenge_id, options: publicKey } = await api<{
		challenge_id: string;
		options: RequestOptionsJSON;
	}>('/auth/passkeys/login/options', { method: 'POST' });
	const credential = (await navigator.credentials.get({
		publicKey: toRequestOptions(publicKey),
		signal: options.signal,
		...(options.conditional ? { mediation: 'conditional' as CredentialMediationRequirement } : {})
	})) as PublicKeyCredential | null;
	if (!credential) return null;
	return api<User>('/auth/passkeys/login/verify', {
		method: 'POST',
		body: { challenge_id, credential: credentialToJSON(credential) }
	});
}

export async function addPasskey(password: string, name: string): Promise<PasskeyInfo> {
	const options = await api<CreationOptionsJSON>('/auth/passkeys/register/options', {
		method: 'POST',
		body: { password }
	});
	const credential = (await navigator.credentials.create({
		publicKey: toCreationOptions(options)
	})) as PublicKeyCredential | null;
	if (!credential) throw new DOMException('Abgebrochen', 'NotAllowedError');
	return api<PasskeyInfo>('/auth/passkeys/register/verify', {
		method: 'POST',
		body: { name, credential: credentialToJSON(credential) }
	});
}
