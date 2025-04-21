require "nvchad.mappings"
-- add custom mapping here

local map = vim.keymap.set

map("n", ";", ":", { desc = "CMD enter command mode" })
map("i", "jk", "<ESC>")

map({ "n", "i", "v" }, "<C-s>", "<cmd> w <cr>")

map("v", "J", ":m '>+1<CR>gv=gv")
map("v", "K", ":m '<-2<CR>gv=gv")

map("n", "J", "mzJ`z")
map("n", "<C-d>", "<C-d>zz")
map("n", "<C-u>", "<C-u>zz")
map("n", "n", "nzzzv")
map("n", "N", "Nzzzv")

map("x", "<leader>p", [["_dP]])
map("n", "Q", "<nop>")

map("n", "<leader><Right>", "<C-w><", { desc = "Decrease width" })
map("n", "<leader><Left>", "<C-w>>", { desc = "Increase width" })
map("n", "<leader><Up>", "<C-w>+", { desc = "Increase height" })
map("n", "<leader><Down>", "<C-w>-", { desc = "Decrease height" })

map("n", "<leader>ft", "<cmd>TodoTelescope<CR>", { desc = "Find Todo" })

map("n", "[d", function()
  vim.diagnostic.jump { count = -1, float = true }
end, { desc = "Previous diagnostic with float" })

map("n", "]d", function()
  vim.diagnostic.jump { count = 1, float = true }
  vim.diagnostic.open_float { scope = "line" }
end, { desc = "Next diagnostic with float" })

map("n", "<leader>fl", function()
  vim.diagnostic.open_float { scope = "line" }
end, { desc = "Show diagnostics float" })

map("n", "K", function()
  vim.lsp.buf.hover { border = "rounded" }
end, { desc = "Show diagnostics float" })
