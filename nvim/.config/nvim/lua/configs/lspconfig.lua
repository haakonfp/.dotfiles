local nvlsp = require "nvchad.configs.lspconfig"
-- local lspconfig = require "lspconfig"

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
  ruff = {
    on_attach = nvlsp.on_attach,
    capabilities = nvlsp.capabilities,
    filetypes = { "python" },
    root_dir = vim.fs.dirname(
      vim.fs.find({ ".git", "setup.py", "setup.cfg", "pyproject.toml", "tox.ini" }, { upward = true })[1]
    ),
    init_options = {
      settings = {
        logLevel = "info",
      },
    },
  },
  ty = {
    cmd = { "ty", "server" },
    filetypes = { "python" },
    root_dir = vim.fs.root(0, { ".git/", "pyproject.toml" }),
    settings = {
      ty = {
        disableLanguageServices = true,
      },
    },
  },
  pyright = {
    settings = {
      pyright = {
        disableOrganizeImports = true,
      },
      python = {
        analysis = {
          ignore = { "*" },
        },
        venvPath = ".venv",
        pythonPath = ".venv/bin/python",
      },
    },
  },
  svelte = {
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
  },
}

for name, opts in pairs(servers) do
  vim.lsp.config(name, opts) -- nvim v0.11.0 or above required
  vim.lsp.enable(name) -- nvim v0.11.0 or above required
end
