-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here

-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here
local map = vim.keymap.set

-- Move selected lines and keep the selection active.
map("v", "J", ":m '>+1<CR>gv=gv", { desc = "Move selection down" })
map("v", "K", ":m '<-2<CR>gv=gv", { desc = "Move selection up" })

-- Keep scrolling and search results centered.
map("n", "<C-d>", "<C-d>zz")
map("n", "<C-u>", "<C-u>zz")
map("n", "n", "nzzzv")
map("n", "N", "Nzzzv")

-- Find text across the project through the existing picker mappings.
map("n", "<leader>fw", "<leader>sg", { remap = true, desc = "Find words (project)" })
map({ "n", "x" }, "<leader>ft", "<leader>sw", { remap = true, desc = "Find this word or selection (project)" })
map("n", "<leader>fl", function()
  Snacks.terminal(nil, { cwd = LazyVim.root() })
end, { desc = "Floating terminal (project)" })

-- yank
map("n", "<leader>fy", function()
  vim.fn.setreg("+", vim.fn.expand("%"))
end, { desc = "Yank file path" })
map("n", "<leader>fY", function()
  vim.fn.setreg("+", string.format("%s:%d", vim.fn.expand("%"), vim.fn.line(".")))
end, { desc = "Yank file name and line to clipboard" })

-- window
map("n", "<C-Left>", "<C-w>h", { desc = "Switch to left window" })
map("n", "<C-Right>", "<C-w>l", { desc = "Switch to right window" })
map("n", "<C-Down>", "<C-w>j", { desc = "Switch to window below" })
map("n", "<C-Up>", "<C-w>k", { desc = "Switch to window above" })
map("n", "=", "<cmd>vertical resize +5<cr>", { desc = "Increase window size vertically" })
map("n", "-", "<cmd>vertical resize -5<cr>", { desc = "Decrease window size vertically" })
map("n", "+", "<cmd>horizontal resize +2<cr>", { desc = "Increase window size horizontally" })
map("n", "_", "<cmd>horizontal resize -2<cr>", { desc = "Decrease window size horizontally" })
