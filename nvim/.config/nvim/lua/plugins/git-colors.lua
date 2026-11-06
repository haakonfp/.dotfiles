return {
  {
    "LazyVim/LazyVim",
    init = function()
      local function git_colors()
        vim.api.nvim_set_hl(0, "Visual", { fg = "#FFFFFF", bg = "#5B4B8A" })
        vim.api.nvim_set_hl(0, "VisualNOS", { fg = "#FFFFFF", bg = "#5B4B8A" })
        vim.api.nvim_set_hl(0, "PmenuSel", { fg = "#FFFFFF", bg = "#5B4B8A", bold = true })
        vim.api.nvim_set_hl(0, "Search", { fg = "#0A0118", bg = "#FFEB66", bold = true })
        vim.api.nvim_set_hl(0, "IncSearch", { fg = "#0A0118", bg = "#33FF44", bold = true })
        vim.api.nvim_set_hl(0, "CurSearch", { fg = "#0A0118", bg = "#33FF44", bold = true })
        for _, group in ipairs({ "GitSignsAdd", "GitSignsAddNr", "GitSignsAddLn", "Added", "diffAdded", "NeoTreeGitAdded" }) do
          vim.api.nvim_set_hl(0, group, { fg = "#33FF44" })
        end
        for _, group in ipairs({ "GitSignsDelete", "GitSignsDeleteNr", "GitSignsDeleteLn", "Removed", "diffRemoved", "NeoTreeGitDeleted" }) do
          vim.api.nvim_set_hl(0, group, { fg = "#FF4D6D" })
        end
        vim.api.nvim_set_hl(0, "DiffAdd", { fg = "#33FF44", bg = "#10351E" })
        vim.api.nvim_set_hl(0, "DiffDelete", { fg = "#FF4D6D", bg = "#40151D" })
      end
      vim.api.nvim_create_autocmd("ColorScheme", { callback = git_colors })
      vim.schedule(git_colors)
    end,
  },
}
