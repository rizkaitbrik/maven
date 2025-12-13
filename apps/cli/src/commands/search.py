import json as json_lib
from pathlib import Path

import typer
from core.actions import SearchActions
from core.actions.search import SearchType
from retrieval.services.config_manager import ConfigManager
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

console = Console()


def search(
    query: str = typer.Argument(..., help="Search query or pattern"),
    root: str = typer.Option(None, help="Search root directory (overrides config)"),
    limit: int = typer.Option(10, help="Max results per page"),
    page: int = typer.Option(1, help="Page number"),
    json: bool = typer.Option(False, help="Output as JSON"),
):
    """Search files using hybrid search (Spotlight + Semantic Content)."""

    # Load configuration from config file and environment
    try:
        config_manager = ConfigManager()
        config = config_manager.config
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load config: {e}[/yellow]")
        console.print("[yellow]Using default configuration...[/yellow]")
        from retrieval.models.config import RetrieverConfig

        config = RetrieverConfig()

    # Override root if specified via CLI
    search_root = Path(root) if root else config.root

    # Initialize search actions
    actions = SearchActions(config=config, root=search_root)

    # Use Hybrid Search by default
    search_type = SearchType.HYBRID
    search_label = "Hybrid Search"

    # Execute search
    # auto_index=True is handled by SearchActions if config allows
    response = actions.search(
        query=query,
        search_type=search_type,
        page=page,
        size=limit,
        auto_index=True, 
    )

    if json:
        results_data = []
        for r in response.results:
            result_dict = {
                "path": r.path, 
                "score": r.score,
                "match_type": r.match_type,
            }
            if r.snippet:
                result_dict["snippet"] = r.snippet
            if r.metadata:
                 result_dict["metadata"] = r.metadata
            
            results_data.append(result_dict)

        print(
            json_lib.dumps(
                {
                    "query": response.query,
                    "page": response.page,
                    "size": response.size,
                    "total": response.total,
                    "search_type": search_type.value,
                    "results": results_data,
                },
                indent=2,
            )
        )
    else:
        # Show pagination info
        # Note: Hybrid/Semantic search often doesn't give precise total count efficiently
        # So we might just show "Results" or "Page X"
        total_str = f"{response.total} total" if response.total > 0 else "found"
        title = f"{search_label}: '{query}' (Page {page}, {total_str})"
        
        console.print(f"\n[bold]{title}[/bold]\n")

        if not response.results:
             console.print("[dim]No results found.[/dim]")
             return

        for i, r in enumerate(response.results, start=1):
            # 1. Header: Path + Match Type + Score
            path_text = Text(r.path, style="cyan underline")
            
            meta_info = []
            if r.match_type:
                 meta_info.append(f"[{r.match_type}]")
            
            # AST Context from metadata
            if r.metadata and "ast_context" in r.metadata:
                 ast_ctx = r.metadata["ast_context"]
                 meta_info.append(f"[bold magenta]{ast_ctx}[/bold magenta]")

            meta_info.append(f"(score: {r.score:.2f})")
            
            header = Text(f"{i}. ") + path_text + Text(" " + " ".join(meta_info), style="dim")
            console.print(header)

            # 2. Snippet
            if r.snippet:
                # Determine language for syntax highlighting
                language = "text"
                if r.metadata and "language" in r.metadata:
                     language = r.metadata["language"]
                elif r.path.endswith(".py"):
                     language = "python"
                elif r.path.endswith(".ts"):
                     language = "typescript"
                
                # Show snippet in panel
                snippet_content = r.snippet.strip()
                if not snippet_content:
                    continue
                    
                syntax = Syntax(snippet_content, language, theme="monokai", line_numbers=False, word_wrap=True)
                console.print(Panel(syntax, border_style="dim", padding=(0, 1)))
            
            console.print("") # Spacer

        # Show navigation hints
        if response.results and len(response.results) >= limit:
            next_hint = f'maven search "{query}" --page {page + 1}'
            console.print(f"[dim]Next page: {next_hint}[/dim]")
        if page > 1:
            prev_hint = f'maven search "{query}" --page {page - 1}'
            console.print(f"[dim]Previous page: {prev_hint}[/dim]")
