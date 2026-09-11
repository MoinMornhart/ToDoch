import { describe, expect, it } from 'vitest';
import {
	base64urlToBuffer,
	bufferToBase64url,
	credentialToJSON,
	isCancelled,
	toCreationOptions,
	toRequestOptions
} from './webauthn';

const bytes = (...values: number[]) => new Uint8Array(values).buffer;

describe('WebAuthn-Umwandlung', () => {
	it('kodiert Base64URL ohne Auffüllzeichen und zurück', () => {
		const data = new Uint8Array([0, 255, 62, 63, 250, 251]);
		const encoded = bufferToBase64url(data);
		expect(encoded).toBe('AP8-P_r7');
		expect(new Uint8Array(base64urlToBuffer(encoded))).toEqual(data);
		expect(new Uint8Array(base64urlToBuffer('AQ'))).toEqual(new Uint8Array([1]));
	});

	it('wandelt Registrierungs-Optionen um', () => {
		const options = toCreationOptions({
			challenge: 'AQID',
			rp: { id: 'todoch.example', name: 'ToDoch' },
			user: { id: 'BAU', name: 'anna@example.org', displayName: 'Anna' },
			pubKeyCredParams: [{ type: 'public-key', alg: -7 }],
			excludeCredentials: [{ id: 'CQ', type: 'public-key', transports: ['internal'] }],
			authenticatorSelection: { residentKey: 'required' }
		});
		expect(new Uint8Array(options.challenge as ArrayBuffer)).toEqual(new Uint8Array([1, 2, 3]));
		expect(new Uint8Array(options.user.id as ArrayBuffer)).toEqual(new Uint8Array([4, 5]));
		expect(options.user.name).toBe('anna@example.org');
		expect(new Uint8Array(options.excludeCredentials![0]!.id as ArrayBuffer)).toEqual(
			new Uint8Array([9])
		);
	});

	it('wandelt Anmelde-Optionen um', () => {
		const options = toRequestOptions({ challenge: 'AQID', rpId: 'todoch.example' });
		expect(options.rpId).toBe('todoch.example');
		expect(options.allowCredentials).toEqual([]);
	});

	it('serialisiert Registrierung und Anmeldung', () => {
		const created = credentialToJSON({
			id: 'AQ',
			rawId: bytes(1),
			type: 'public-key',
			authenticatorAttachment: 'platform',
			response: {
				clientDataJSON: bytes(2),
				attestationObject: bytes(3),
				getTransports: () => ['internal']
			} as unknown as AuthenticatorResponse
		});
		expect(created).toMatchObject({
			rawId: 'AQ',
			response: { clientDataJSON: 'Ag', attestationObject: 'Aw', transports: ['internal'] }
		});

		const asserted = credentialToJSON({
			id: 'AQ',
			rawId: bytes(1),
			type: 'public-key',
			response: {
				clientDataJSON: bytes(2),
				authenticatorData: bytes(4),
				signature: bytes(5),
				userHandle: null
			} as unknown as AuthenticatorResponse
		});
		expect(asserted.response).toEqual({
			clientDataJSON: 'Ag',
			authenticatorData: 'BA',
			signature: 'BQ',
			userHandle: null
		});
	});

	it('erkennt Abbrüche', () => {
		expect(isCancelled(new DOMException('x', 'NotAllowedError'))).toBe(true);
		expect(isCancelled(new DOMException('x', 'AbortError'))).toBe(true);
		expect(isCancelled(new DOMException('x', 'InvalidStateError'))).toBe(false);
		expect(isCancelled(new Error('x'))).toBe(false);
	});
});
