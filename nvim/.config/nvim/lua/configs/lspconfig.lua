local nvlsp = require "nvchad.configs.lspconfig"
local lspconfig = require "lspconfig"

nvlsp.defaults()

local servers = {
  html = {},
  cssls = {},
  ts_ls = {
    init_options = {
      preferences = {
        disableSuggestions = true,
      },
    },
  },
  tailwindcss = {
    filetypes = { "html", "svelte" },
    init_options = {
      userLanguages = {
        svelte = "html",
      },
    },
  },
  lua_ls = {},
  prismals = {
    filetypes = { "prisma" },
  },
}

for name, opts in pairs(servers) do
  vim.lsp.enable(name) -- nvim v0.11.0 or above required
  vim.lsp.config(name, opts) -- nvim v0.11.0 or above required
end

lspconfig.svelte.setup {
  filetypes = { "svelte" },
  on_attach = function(client, bufnr)
    if client.name == "svelte" then
      vim.api.nvim_create_autocmd("BufWritePost", {
        pattern = { "*.js", "*.ts", "*.svelte" },
        callback = function(ctx)
          client.notify("$/onDidChangeTsOrJsFile", { uri = ctx.file })
        end,
      })
    end
    if vim.bo[bufnr].filetype == "svelte" then
      vim.api.nvim_create_autocmd("BufWritePost", {
        pattern = { "*.js", "*.ts", "*.svelte" },
        callback = function(ctx)
          client.notify("$/onDidChangeTsOrJsFile", { uri = ctx.file })
        end,
      })
    end
  end,
  capabilities = nvlsp.capabilities,
}

-- lspconfig.rust_analyzer.setup {
--   -- cmd = { "/home/hfp/dev/hfp/rust-analyzer/target/release/rust-analyzer" },
--   on_attach = nvlsp.on_attach,
--   capabilities = nvlsp.capabilities,
--   filetypes = { "rust" },
--   root_dir = lspconfig.util.root_pattern "Cargo.toml",
--   settings = {
--     ["rust-analyzer"] = {
--       imports = {
--         granularity = {
--           group = "module",
--         },
--         prefix = "self",
--       },
--       cargo = {
--         allFeatures = true,
--         buildScripts = {
--           enable = true,
--         },
--       },
--       procMacro = {
--         enable = true,
--       },
--     },
--   },
-- }
