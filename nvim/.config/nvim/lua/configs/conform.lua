local options = {
  formatters_by_ft = {
    lua = { "stylua" },
    css = { "prettierd", "prettier" },
    html = { "prettierd", "prettier" },
    rust = { "rustfmt" },
    javascript = { "prettierd", "prettier" },
    typescript = { "prettierd", "prettier" },
    svelte = { "prettierd", "prettier" },
    json = { "prettierd", "prettier" },
  },

  format_on_save = {
    -- timeout_ms = 500,
    lsp_format = "fallback",
  },
}

return options
