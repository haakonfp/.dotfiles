return {
  {
    "nvim-neo-tree/neo-tree.nvim",
    keys = {
      { "<C-n>", "<cmd>Neotree toggle filesystem left<cr>", desc = "Toggle file tree" },
    },
    dependencies = {
      {
        "s1n7ax/nvim-window-picker",
        version = "2.*",
        opts = {
          hint = "floating-big-letter",
          selection_chars = "AOEUIDHTNSQJKXBMWVZPYFGCRL",
          filter_rules = {
            include_current_win = false,
            autoselect_one = true,
            bo = {
              filetype = { "neo-tree", "neo-tree-popup", "notify" },
              buftype = { "terminal", "quickfix" },
            },
          },
        },
        config = function(_, opts)
          require("window-picker").setup(opts)
        end,
      },
    },
    opts = function(_, opts)
      local ignored_filetypes = { "neo-tree", "neo-tree-popup", "notify" }
      local ignored_buftypes = { "terminal", "quickfix" }

      local function pickable_windows()
        local current_win = vim.api.nvim_get_current_win()
        local windows = {}

        for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
          if win ~= current_win and vim.api.nvim_win_is_valid(win) then
            local buf = vim.api.nvim_win_get_buf(win)
            local bo = vim.bo[buf]

            if
              not vim.tbl_contains(ignored_filetypes, bo.filetype)
              and not vim.tbl_contains(ignored_buftypes, bo.buftype)
            then
              windows[#windows + 1] = win
            end
          end
        end

        return windows
      end

      local function open_command(command)
        return function(state)
          local node = state.tree:get_node()
          local is_file = node and node.type == "file"

          if is_file and #pickable_windows() > 1 then
            local ok, picker = pcall(require, "window-picker")

            if ok then
              local picked_win = picker.pick_window({})

              if not picked_win then
                return
              end

              vim.api.nvim_set_current_win(picked_win)

              local current_position = state.current_position
              state.current_position = "current"
              local opened, err = pcall(state.commands[command], state)
              state.current_position = current_position

              if not opened then
                error(err)
              end
            else
              state.commands[command](state)
            end
          else
            state.commands[command](state)
          end
        end
      end

      opts.commands = opts.commands or {}
      opts.commands.toggle_node_or_preview = function(state)
        local node = state.tree:get_node()
        if not node then
          return
        end
        if node.type == "directory" then
          state.commands.toggle_node(state)
        elseif node.type == "file" then
          state.commands.toggle_preview(state)
        end
      end
      opts.commands.expand_directory = function(state)
        local node = state.tree:get_node()
        if node and node.type == "directory" and not node:is_expanded() then
          state.commands.toggle_node(state)
        end
      end
      opts.commands.open_keep_tree = open_command("open")
      opts.commands.open_split_keep_tree = open_command("open_split")
      opts.commands.open_vsplit_keep_tree = open_command("open_vsplit")

      opts.window = opts.window or {}
      opts.window.mappings = opts.window.mappings or {}
      opts.window.mappings["<tab>"] = nil
      opts.window.mappings["<cr>"] = "open_keep_tree"
      opts.window.mappings["<Tab>"] = { "toggle_node_or_preview", config = { use_float = false } }
      opts.window.mappings["<Right>"] = "expand_directory"
      opts.window.mappings["<Left>"] = "close_node"
      opts.window.mappings["S"] = "open_split_keep_tree"
      opts.window.mappings["s"] = "open_vsplit_keep_tree"
    end,
  },
}
