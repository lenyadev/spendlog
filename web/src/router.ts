import { createRouter } from "sv-router";
import Home from "./routes/Home.svelte";
import Login from "./routes/Login.svelte";

export const { p, navigate, isActive, route } = createRouter({
  "/": Home,
  "/login": Login,
});
