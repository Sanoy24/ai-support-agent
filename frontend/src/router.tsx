import { createBrowserRouter } from "react-router";

import { ConversationDetail } from "@/pages/admin/ConversationDetail";
import { Conversations } from "@/pages/admin/Conversations";
import { Inbox } from "@/pages/admin/Inbox";
import { AdminLayout } from "@/pages/admin/Layout";
import { Login } from "@/pages/admin/Login";
import { Overview } from "@/pages/admin/Overview";
import { Unanswered } from "@/pages/admin/Unanswered";
import { NotFound } from "@/pages/NotFound";
import { Storefront } from "@/pages/Storefront";

export const router = createBrowserRouter([
  { path: "/", element: <Storefront /> },
  { path: "/admin/login", element: <Login /> },
  {
    path: "/admin",
    element: <AdminLayout />,
    children: [
      { index: true, element: <Overview /> },
      { path: "inbox", element: <Inbox /> },
      { path: "unanswered", element: <Unanswered /> },
      { path: "conversations", element: <Conversations /> },
      { path: "conversations/:id", element: <ConversationDetail /> },
    ],
  },
  { path: "*", element: <NotFound /> },
]);
