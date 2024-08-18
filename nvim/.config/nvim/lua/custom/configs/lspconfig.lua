local config = require "plugins.configs.lspconfig"
local on_attach = config.on_attach
local capabilities = config.capabilities

local lspconfig = require "lspconfig"

local function organize_imports()
  local params = {
    command = "_typescript.organizeImports",
    arguments = { vim.api.nvim_buf_get_name(0) },
  }
  vim.lsp.buf.execute_command(params)
end

lspconfig.tsserver.setup {
  on_attach = function(client, bfnr)
    on_attach(client, bfnr)
    vim.api.nvim_create_user_command("OrganizeImports", organize_imports, { desc = "Organize Imports" })
  end,
  capabilities = capabilities,
  init_options = {
    preferences = {
      disableSuggestions = true,
    },
  },
}

lspconfig.ruff_lsp.setup {
  on_attach = on_attach,
  capabilities = capabilities,
  filetypes = { "python" },
}

lspconfig.pyright.setup {
  on_attach = on_attach,
  capabilities = capabilities,
  filetypes = { "python" },
  settings = {
    pyright = {
      disableOrganizeImports = true,
      disableTaggedHints = true,
    },
    python = {
      analysis = {
        diagnosticSeverityOverrides = {
          -- https://github.com/microsoft/pyright/blob/main/docs/configuration.md#type-check-diagnostics-settings
          reportUndefinedVariable = "none",
        },
      },
    },
  },
}

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
  capabilities = capabilities,
}

lspconfig.tailwindcss.setup {
  on_attach = on_attach,
  capabilities = capabilities,
  filetypes = { "html", "svelte" },
}

lspconfig.prismals.setup {
  on_attach = on_attach,
  capabilities = capabilities,
  filetypes = { "prisma" },
}

lspconfig.lua_ls.setup {
  on_attach = on_attach,
  capabilities = capabilities,
  filetypes = { "lua" },
}

lspconfig.rust_analyzer.setup {
  -- cmd = { "/home/hfp/dev/hfp/rust-analyzer/target/release/rust-analyzer" },
  on_attach = on_attach,
  capabilities = capabilities,
  filetypes = { "rust" },
  root_dir = lspconfig.util.root_pattern "Cargo.toml",
  settings = {
    ["rust-analyzer"] = {
      imports = {
        granularity = {
          group = "module",
        },
        prefix = "self",
      },
      cargo = {
        allFeatures = true,
        buildScripts = {
          enable = true,
        },
      },
      procMacro = {
        enable = true,
      },
    },
  },
}

lspconfig.solidity.setup {
  cmd = { "nomicfoundation-solidity-language-server", "--stdio" },
  on_attach = on_attach,
  capabilities = capabilities,
  filetypes = { "solidity" },
}
