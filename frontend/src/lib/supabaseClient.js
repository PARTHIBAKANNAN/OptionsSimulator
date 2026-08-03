import { createClient } from "@supabase/supabase-js";

// Deliberately no fallback values. `npm run build` bundles this without executing it, so a
// missing env var won't fail the build — but createClient() throws synchronously the moment this
// module actually runs (page load in the browser), which is loud enough to notice immediately.
export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
);
