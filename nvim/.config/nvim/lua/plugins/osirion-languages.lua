-- Language servers and formatters for the Osirion monorepo.
return {

  {
    "mason-org/mason.nvim",
    opts = function(_, opts)
      opts.ensure_installed = opts.ensure_installed or {}
      for _, tool in ipairs({
        "vtsls",
        "html-lsp",
        "css-lsp",
        "tailwindcss-language-server",
        "svelte-language-server",
        "eslint-lsp",
        "prettier",
        "lua-language-server",
        "stylua",
        "prisma-language-server",
        "sqlls",
        "rust-analyzer",
        "omnisharp",
        "csharpier",
        "ty",
        "ruff",
        "black",
        "json-lsp",
        "yaml-language-server",
        "terraform-ls",
        "dockerfile-language-server",
        "bash-language-server",
        "buf",
      }) do
        if not vim.tbl_contains(opts.ensure_installed, tool) then
          table.insert(opts.ensure_installed, tool)
        end
      end
    end,
  },
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        html = {},
        cssls = {},
        lua_ls = {},
        sqlls = {},
        rust_analyzer = {},
        omnisharp = {
          settings = {
            RoslynExtensionsOptions = {
              EnableAnalyzersSupport = true,
              EnableImportCompletion = true,
            },
          },
        },
        -- ty discovers uv's project .venv; uv itself is not an LSP server.
        ty = {},
        ruff = {},
        pyright = { enabled = false },
        basedpyright = { enabled = false },
        ruff_lsp = { enabled = false },
        eslint = { settings = { workingDirectories = { mode = "auto" } } },
        jsonls = {},
        yamlls = {},
        terraformls = {},
        dockerls = {},
        bashls = {},
        buf_ls = {},
      },
      setup = {
        ruff = function()
          Snacks.util.lsp.on({ name = "ruff" }, function(_, client)
            client.server_capabilities.hoverProvider = false
            -- Keep Black as the sole Python formatter.
            client.server_capabilities.documentFormattingProvider = false
            client.server_capabilities.documentRangeFormattingProvider = false
          end)
        end,
      },
    },
  },
  {
    "stevearc/conform.nvim",
    opts = {
      formatters_by_ft = {
        python = { "black" },
        cs = { "csharpier" },
        rust = { "rustfmt" },
        -- Use the repo's Prettier and its Svelte/Prisma/Tailwind plugins.
        svelte = { "prettier" },
        prisma = { "prettier" },
      },
    },
  },
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = opts.ensure_installed or {}
      for _, parser in ipairs({
        "typescript",
        "tsx",
        "javascript",
        "html",
        "css",
        "svelte",
        "lua",
        "prisma",
        "sql",
        "rust",
        "c_sharp",
        "python",
        "json",
        "jsonc",
        "yaml",
        "toml",
        "hcl",
        "terraform",
        "dockerfile",
        "bash",
        "proto",
      }) do
        if not vim.tbl_contains(opts.ensure_installed, parser) then
          table.insert(opts.ensure_installed, parser)
        end
      end
    end,
  },
}
