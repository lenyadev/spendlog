<script lang="ts">
  import { onMount } from "svelte";
  import { request } from "$lib/api/client";
  import { ApiError } from "$lib/api/errors";
  import type { paths } from "$lib/api/schema";

  type Health =
    paths["/health"]["get"]["responses"]["200"]["content"]["application/json"];

  let status = $state<"loading" | "success" | "error">("loading");
  let data = $state<Health | null>(null);
  let errorMessage = $state("");

  onMount(async () => {
    try {
      data = await request<Health>("GET", "/health");
      status = "success";
    } catch (e) {
      errorMessage =
        e instanceof ApiError
          ? `Ошибка ${e.status}: ${e.message}`
          : "Бэкенд недоступен";
      status = "error";
    }
  });
</script>

<div class="card bg-base-100 shadow-sm">
  <div class="card-body">
    <h2 class="card-title">Состояние бэкенда</h2>
    {#if status == "loading"}
      <p>Загрузка...</p>
    {:else if status == "error"}
      <p>{errorMessage}</p>
    {:else}
      <pre>{JSON.stringify(data, null, 2)}</pre>
    {/if}
    <div class="card-actions justify-end">
      <button class="btn btn-primary btn-sm">Кнопка</button>
    </div>
  </div>
</div>