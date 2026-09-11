import { describe, expect, it } from 'vitest';
import { urlBase64ToBytes } from './push';

describe('push', () => {
	it('decodes base64url keys', () => {
		expect(Array.from(urlBase64ToBytes('AQID'))).toEqual([1, 2, 3]);
		expect(Array.from(urlBase64ToBytes('_-8'))).toEqual([255, 239]);
		const key = 'B' + 'A'.repeat(86);
		expect(urlBase64ToBytes(key)).toHaveLength(65);
	});
});
