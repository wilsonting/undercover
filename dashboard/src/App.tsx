import { ClaimPage } from "./pages/Claim";
import { Instructions } from "./pages/Instructions";
import { Queue } from "./pages/Queue";
import { useRoute } from "./router";

export function App() {
  const route = useRoute();

  return (
    <>
      <header className="header">
        <a className="brand" href="#/">
          UnderCover
        </a>
        <span className="tagline">Claims desk</span>
        <nav className="nav">
          <a
            href="#/"
            aria-current={route.page === "queue" ? "page" : undefined}
          >
            Queue
          </a>
          <a
            href="#/instructions"
            aria-current={route.page === "instructions" ? "page" : undefined}
          >
            Instructions
          </a>
        </nav>
      </header>
      <main>
        {route.page === "queue" && <Queue />}
        {route.page === "claim" && (
          <ClaimPage key={route.claimId} claimId={route.claimId} />
        )}
        {route.page === "instructions" && <Instructions />}
      </main>
    </>
  );
}
