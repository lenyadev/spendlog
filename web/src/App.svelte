<script lang="ts">
  import { Router } from "sv-router";
  import "./router";
</script>

<div class="min-h-screen">
  <header class="navbar bg-base-100 border-b border-base-300">
    <div class="mx-auto flex w-full max-w-3xl items-center justify-between px-4">
      <a href="/" class="text-lg font-semibold text-primary">Spendlog</a>
      <nav class="flex gap-2">
        <a href="/" class="btn btn-ghost btn-sm">Главная</a>
        <a href="/login" class="btn btn-ghost btn-sm">Вход</a>
      </nav>
    </div>
  </header>

  <main class="mx-auto max-w-3xl p-4">
    <Router />
  </main>

</div>