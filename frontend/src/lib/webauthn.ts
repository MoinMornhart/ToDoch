/**
 * WebAuthn im Browser: Optionen vom Server (JSON, Base64URL) in die Form bringen, die
 * navigator.credentials erwartet – und die Antwort wieder als JSON zurück. Bewusst ohne
 * PublicKeyCredential.parse…FromJSON, damit auch ältere Browser funktionieren.
 */

export function bufferToBase64url(data: ArrayBuffer | Uint8Array): string {
	const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
	let binary = '';
	for (const byte of bytes) binary += String.fromCharCode(byte);
	return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function base64urlToBuffer(value: string): ArrayBuffer {
	const base64 = value.replace(/-/g, '+').replace(/_/g, '/');
	const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
	const binary = atob(padded);
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
	return bytes.buffer;
}

interface DescriptorJSON {
	id: string;
	type: 'public-key';
	transports?: AuthenticatorTransport[];
}

export interface CreationOptionsJSON {
	challenge: string;
	rp: PublicKeyCredentialRpEntity;
	user: { id: string; name: string; displayName: string };
	pubKeyCredParams: PublicKeyCredentialParameters[];
	timeout?: number;
	excludeCredentials?: DescriptorJSON[];
	authenticatorSelection?: AuthenticatorSelectionCriteria;
	attestation?: AttestationConveyancePreference;
}

export interface RequestOptionsJSON {
	challenge: string;
	timeout?: number;
	rpId?: string;
	allowCredentials?: DescriptorJSON[];
	userVerification?: UserVerificationRequirement;
}

function descriptor(item: DescriptorJSON): PublicKeyCredentialDescriptor {
	return { type: item.type, id: base64urlToBuffer(item.id), transports: item.transports };
}

export function toCreationOptions(json: CreationOptionsJSON): PublicKeyCredentialCreationOptions {
	return {
		challenge: base64urlToBuffer(json.challenge),
		rp: json.rp,
		user: { ...json.user, id: base64urlToBuffer(json.user.id) },
		pubKeyCredParams: json.pubKeyCredParams,
		timeout: json.timeout,
		excludeCredentials: (json.excludeCredentials ?? []).map(descriptor),
		authenticatorSelection: json.authenticatorSelection,
		attestation: json.attestation
	};
}

export function toRequestOptions(json: RequestOptionsJSON): PublicKeyCredentialRequestOptions {
	return {
		challenge: base64urlToBuffer(json.challenge),
		timeout: json.timeout,
		rpId: json.rpId,
		allowCredentials: (json.allowCredentials ?? []).map(descriptor),
		userVerification: json.userVerification
	};
}

type AnyResponse = {
	clientDataJSON: ArrayBuffer;
	attestationObject?: ArrayBuffer;
	authenticatorData?: ArrayBuffer;
	signature?: ArrayBuffer;
	userHandle?: ArrayBuffer | null;
	getTransports?: () => string[];
};

export function credentialToJSON(credential: {
	id: string;
	rawId: ArrayBuffer;
	type: string;
	response: AuthenticatorResponse;
	authenticatorAttachment?: string | null;
}): Record<string, unknown> {
	const response = credential.response as unknown as AnyResponse;
	const body: Record<string, unknown> = {
		clientDataJSON: bufferToBase64url(response.clientDataJSON)
	};
	if (response.attestationObject) {
		body.attestationObject = bufferToBase64url(response.attestationObject);
		body.transports = response.getTransports?.() ?? [];
	} else {
		body.authenticatorData = bufferToBase64url(response.authenticatorData!);
		body.signature = bufferToBase64url(response.signature!);
		body.userHandle = response.userHandle ? bufferToBase64url(response.userHandle) : null;
	}
	return {
		id: credential.id,
		rawId: bufferToBase64url(credential.rawId),
		type: credential.type,
		response: body,
		clientExtensionResults: {},
		authenticatorAttachment: credential.authenticatorAttachment ?? undefined
	};
}

/** Passkeys gehen nur in sicheren Kontexten (HTTPS oder localhost). */
export function passkeysSupported(): boolean {
	return (
		typeof window !== 'undefined' &&
		window.isSecureContext &&
		typeof window.PublicKeyCredential === 'function' &&
		!!navigator.credentials
	);
}

/** Passkeys direkt im Autofill des E-Mail-Felds vorschlagen („conditional mediation“). */
export async function autofillSupported(): Promise<boolean> {
	if (!passkeysSupported()) return false;
	try {
		return (await PublicKeyCredential.isConditionalMediationAvailable?.()) ?? false;
	} catch {
		return false;
	}
}

/** Abbruch durch die Person (Dialog geschlossen) statt eines echten Fehlers? */
export function isCancelled(error: unknown): boolean {
	return (
		error instanceof DOMException &&
		(error.name === 'NotAllowedError' || error.name === 'AbortError')
	);
}
