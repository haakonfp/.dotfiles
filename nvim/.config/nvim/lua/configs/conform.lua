local options = {
  formatters_by_ft = {
    lua = { "stylua" },
    css = { "prettierd" },
    html = { "prettierd" },
    rust = { "rustfmt" },
    javascript = { "prettierd" },
    typescript = { "prettierd" },
    svelte = { "prettierd" },
    json = { "prettierd" },
    python = { "ruff_fix", "ruff_format", "ruff_organize_imports" },
  },

  format_on_save = {
    -- timeout_ms = 500,
    lsp_format = "fallback",
  },
}

return options
