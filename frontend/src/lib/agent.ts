/** Kurzbeschreibung eines User-Agents für die Geräteliste, z. B. „Firefox · Windows“. */
export function describeAgent(userAgent: string | null): string {
	if (!userAgent) return '–';
	const browser = /Edg\//.test(userAgent)
		? 'Edge'
		: /Firefox\//.test(userAgent)
			? 'Firefox'
			: /Chrome\//.test(userAgent)
				? 'Chrome'
				: /Safari\//.test(userAgent)
					? 'Safari'
					: null;
	const system = /iPhone|iPad/.test(userAgent)
		? 'iOS'
		: /Android/.test(userAgent)
			? 'Android'
			: /Windows/.test(userAgent)
				? 'Windows'
				: /Mac OS X|Macintosh/.test(userAgent)
					? 'macOS'
					: /Linux/.test(userAgent)
						? 'Linux'
						: null;
	const parts = [browser, system].filter(Boolean);
	return parts.length ? parts.join(' · ') : userAgent.slice(0, 60);
}
