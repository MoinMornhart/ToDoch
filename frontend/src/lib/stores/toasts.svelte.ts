export interface ToastAction {
	label: string;
	run: () => void | Promise<void>;
}

export interface Toast {
	id: number;
	message: string;
	kind: 'info' | 'error';
	action?: ToastAction;
}

let nextId = 1;

class Toasts {
	items = $state<Toast[]>([]);

	show(message: string, options: { kind?: Toast['kind']; action?: ToastAction } = {}): void {
		const toast: Toast = {
			id: nextId++,
			message,
			kind: options.kind ?? 'info',
			action: options.action
		};
		this.items = [...this.items.slice(-2), toast];
		setTimeout(() => this.dismiss(toast.id), toast.action ? 6000 : 3500);
	}

	error(message: string): void {
		this.show(message, { kind: 'error' });
	}

	dismiss(id: number): void {
		this.items = this.items.filter((t) => t.id !== id);
	}
}

export const toasts = new Toasts();
