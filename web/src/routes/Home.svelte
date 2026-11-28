<script lang="ts">
    import { onMount } from "svelte";
    import { request } from '$lib/api/client';
    import { ApiError } from "$lib/api/errors";
    import type { paths } from '$lib/api/schema';

    type Health = 
        paths['/health']['get']['responses']['200']['content']['application/json'];
    
    let status = $state<'loading' | 'success' | 'error'>('loading');
    let data = $state<Health | null>(null);
    let errorMessage = $state('');

    onMount(async () => {
        try {
            data = await request<Health>('GET', '/health');
            status = 'success';
        } catch (e) {
            errorMessage = 
                e instanceof ApiError
                ? `Ошибка ${e.status}: ${e.message}`
                : 'Бэкенд недоступен';
            status = 'error';
        }
    });
</script>


<h1>Главная</h1>

{#if status == 'loading'}
    <p>Загрузка...</p>
{:else if status == 'error'} 
    <p>{errorMessage}</p>
{:else}
    <pre>{JSON.stringify(data, null, 2)}</pre>
{/if}