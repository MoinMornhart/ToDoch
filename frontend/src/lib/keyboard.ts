/** Tastaturkürzel: nie auslösen, während in ein Feld getippt wird. */

export function isTypingTarget(target: EventTarget | null): boolean {
	if (!target || typeof (target as HTMLElement).tagName !== 'string') return false;
	const element = target as HTMLElement;
	if (element.isContentEditable) return true;
	const tag = element.tagName.toLowerCase();
	if (tag === 'textarea' || tag === 'select') return true;
	if (tag !== 'input') return false;
	const type = (element as HTMLInputElement).type;
	return !['checkbox', 'radio', 'button', 'submit', 'reset', 'range', 'color'].includes(type);
}

/** Liefert die gedrückte Taste für einfache Kürzel oder `null`. */
export function plainKey(event: KeyboardEvent): string | null {
	if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return null;
	if (event.isComposing) return null;
	if (isTypingTarget(event.target)) return null;
	return event.key;
}
