/** Rückfragen mit mehreren Antworten („Nur dieser Termin / alle folgenden / alle“). */

export interface ChoiceOption {
	value: string;
	label: string;
	primary?: boolean;
	danger?: boolean;
}

interface ChoiceRequest {
	title: string;
	message: string;
	options: ChoiceOption[];
	resolve: (value: string | null) => void;
}

class Choice {
	request = $state<ChoiceRequest | null>(null);

	ask(title: string, message: string, options: ChoiceOption[]): Promise<string | null> {
		this.request?.resolve(null);
		return new Promise((resolve) => {
			this.request = { title, message, options, resolve };
		});
	}

	answer(value: string | null): void {
		const request = this.request;
		this.request = null;
		request?.resolve(value);
	}
}

export const choice = new Choice();
