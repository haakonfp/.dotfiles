require "nvchad.options"
-- add custom options here

-- local o = vim.o
-- o.cursorlineopt = "both" -- enable cursorline. note: does not work with transparent theme

local wo = vim.wo
wo.relativenumber = true

local fn = vim.fn
fn.setenv("CARGO_TARGET_DIR", "target/analyzer")

local signs = { Error = " ", Warn = " ", Hint = " ", Info = " " }
for type, icon in pairs(signs) do
  local hl = "DiagnosticSign" .. type
  vim.fn.sign_define(hl, { text = icon, texthl = hl, numhl = hl })
end

-----------
-- autocmds
-----------

-- vim.api.nvim_create_autocmd("BufWritePre", {
--   pattern = "*",
--   callback = function(args)
--       require("configs.conform").format({ bufnr = args.buf })
--   end,
-- })
