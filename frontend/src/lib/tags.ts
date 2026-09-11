/** Tags aus Freitext: „#Haushalt, finanzen amt“ → ["haushalt", "finanzen", "amt"]. */
export function parseTags(text: string, max = 20): string[] {
	const tags: string[] = [];
	for (const raw of text.split(/[\s,;]+/)) {
		const tag = raw.replace(/^#+/, '').toLowerCase().slice(0, 40);
		if (tag && /^[\p{L}\p{N}_-]+$/u.test(tag) && !tags.includes(tag)) tags.push(tag);
		if (tags.length >= max) break;
	}
	return tags;
}
