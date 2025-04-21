local M = {}

M.treesitter = {
  ensure_installed = {
    "vim",
    "lua",
    "vimdoc",
    "html",
    "css",
    "typescript",
    "javascript",
    "python",
    "rust",
    "svelte",
    "prisma",
    "c_sharp",
    "markdown",
    "json",
  },
  indent = {
    enable = true,
  },
}

M.mason = {
  ensure_installed = {
    "lua-language-server",
    "css-lsp",
    "html-lsp",
    "prettierd",
    "eslint_d",
    "prisma-language-server",
    "rust-analyzer",
    "stylua",
    "svelte-language-server",
    "tailwindcss-language-server",
    "typescript-language-server",
    "gopls",
  },
}

-- git support in nvimtree
M.nvimtree = {
  git = {
    enable = false,
  },

  renderer = {
    highlight_git = true,
    icons = {
      show = {
        git = true,
      },
    },
  },
}

return M
