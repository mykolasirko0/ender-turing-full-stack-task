import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
  type QueryKey,
} from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import { AxiosError } from "axios"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"
import { client } from "./client/client.gen"
import { ThemeProvider } from "./components/theme-provider"
import { Toaster } from "./components/ui/sonner"
import "./index.css"
import { routeTree } from "./routeTree.gen"

client.setConfig({
  baseURL: import.meta.env.VITE_API_URL ?? "",
  auth: () => localStorage.getItem("access_token") || "",
})

const CURRENT_USER_KEY = "currentUser"

// 401: not (or no longer) authenticated -> log out.
// 403: authenticated but not allowed -> the user's role may have changed, so
// refetch /users/me; the sidebar, guards and pages then re-render from the
// fresh permissions. The failing call's own onError still shows its toast.
const handleApiError = (error: Error, failedKey?: QueryKey) => {
  if (!(error instanceof AxiosError)) return
  const status = error.response?.status
  if (status === 401) {
    localStorage.removeItem("access_token")
    window.location.href = "/login"
  } else if (status === 403 && failedKey?.[0] !== CURRENT_USER_KEY) {
    // (guard against a refetch loop should /users/me itself ever return 403)
    queryClient.invalidateQueries({ queryKey: [CURRENT_USER_KEY] })
  }
}
const MAX_QUERY_RETRIES = 3

// Auth errors won't fix themselves: don't retry, so the handler above runs
// right away instead of after the default retry backoff (~7s).
const shouldRetryQuery = (failureCount: number, error: Error) => {
  const status =
    error instanceof AxiosError ? error.response?.status : undefined
  if (status === 401 || status === 403) return false
  return failureCount < MAX_QUERY_RETRIES
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: shouldRetryQuery },
  },
  queryCache: new QueryCache({
    onError: (error, query) => handleApiError(error, query.queryKey),
  }),
  mutationCache: new MutationCache({
    onError: (error) => handleApiError(error),
  }),
})

const router = createRouter({ routeTree })
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
        <Toaster richColors closeButton />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
)
