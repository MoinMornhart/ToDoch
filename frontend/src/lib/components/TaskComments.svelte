<script lang="ts">
	import { MessageSquare, Trash } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { toasts } from '$lib/stores/toasts.svelte';

	interface Comment {
		id: string;
		author_name: string;
		body: string;
		body_html: string;
		created_at: string;
		mine: boolean;
	}

	/** Kommentare an einer Aufgabe – sitzt im Aufgaben-Formular, daher kein eigenes <form>. */
	let { taskId, canWrite, canManage }: { taskId: string; canWrite: boolean; canManage: boolean } =
		$props();
	const uid = $props.id();
	let comments = $state<Comment[]>([]);
	let text = $state('');
	let busy = $state(false);

	function report(error: unknown) {
		toasts.error(error instanceof ApiError ? error.message : t('error.generic'));
	}

	function when(value: string): string {
		return new Intl.DateTimeFormat(i18n.locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
			new Date(value)
		);
	}

	onMount(async () => {
		try {
			comments = await api<Comment[]>(`/tasks/${taskId}/comments`);
		} catch (error) {
			report(error);
		}
	});

	async function post() {
		const body = text.trim();
		if (!body || busy) return;
		busy = true;
		try {
			const created = await api<Comment>(`/tasks/${taskId}/comments`, {
				method: 'POST',
				body: { body }
			});
			comments = [...comments, created];
			text = '';
		} catch (error) {
			report(error);
		} finally {
			busy = false;
		}
	}

	async function remove(comment: Comment) {
		try {
			await api(`/tasks/${taskId}/comments/${comment.id}`, { method: 'DELETE' });
			comments = comments.filter((c) => c.id !== comment.id);
		} catch (error) {
			report(error);
		}
	}

	/** Strg+Enter schickt den Kommentar ab – und nicht das Aufgaben-Formular. */
	function onKeydown(event: KeyboardEvent) {
		if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
			event.preventDefault();
			event.stopPropagation();
			void post();
		}
	}
</script>

<section class="border-t border-line pt-4" aria-labelledby="{uid}-title">
	<h3 id="{uid}-title" class="label flex items-center gap-1">
		<MessageSquare size={14} aria-hidden="true" />{t('comments.title')}
	</h3>
	{#if comments.length}
		<ul class="mb-3 flex flex-col gap-3">
			{#each comments as comment (comment.id)}
				<li class="text-sm">
					<p class="flex items-center gap-2 text-xs text-muted">
						<span class="font-medium text-fg">{comment.author_name}</span>
						<span>{when(comment.created_at)}</span>
						{#if comment.mine || canManage}
							<button
								type="button"
								class="icon-btn ml-auto hover:text-danger"
								aria-label={t('comments.delete')}
								onclick={() => remove(comment)}
							>
								<Trash size={12} aria-hidden="true" />
							</button>
						{/if}
					</p>
					<!-- Serverseitig per Allowlist bereinigtes HTML -->
					<div class="prose-notes">{@html comment.body_html}</div>
				</li>
			{/each}
		</ul>
	{:else}
		<p class="mb-3 text-sm text-muted">{t('comments.none')}</p>
	{/if}
	{#if canWrite}
		<textarea
			class="input min-h-16"
			maxlength="5000"
			placeholder={t('comments.placeholder')}
			aria-label={t('comments.title')}
			bind:value={text}
			onkeydown={onKeydown}></textarea>
		<button type="button" class="btn mt-2" disabled={busy || !text.trim()} onclick={post}>
			{t('comments.add')}
		</button>
	{/if}
</section>
