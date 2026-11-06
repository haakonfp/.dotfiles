-- Omarchy generates themes; other Linux hosts use the portable Agamotto spec.
local current = vim.fn.expand("~/.local/state/omarchy/current/theme/neovim.lua")
local portable = vim.fn.expand("~/.config/dotfiles/themes/agamotto/neovim.lua")
return dofile(vim.fn.filereadable(current) == 1 and current or portable)
