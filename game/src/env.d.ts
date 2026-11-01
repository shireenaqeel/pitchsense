/// <reference types="vite/client" />

// Build-time settings for the shared leaderboards (see systems/leaderboard.ts).
// Both are public by design: they end up in the page every player downloads.
interface ImportMetaEnv {
  readonly VITE_SUPABASE_URL?: string;
  readonly VITE_SUPABASE_KEY?: string;
}
