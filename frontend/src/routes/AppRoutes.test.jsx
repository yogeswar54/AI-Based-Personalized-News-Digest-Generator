import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Login from "../pages/Login.jsx";
import Register from "../pages/Register.jsx";
import { GuestRoute, ProtectedRoute } from "../components/ProtectedRoute.jsx";
import { useAuth } from "../context/AuthContext.jsx";

vi.mock("../context/AuthContext.jsx", () => ({ useAuth: vi.fn() }));

function renderWithRoutes(element, path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={element} />
        <Route path="/dashboard" element={<p>Dashboard page</p>} />
        <Route path="/interest-selection" element={<p>Interest selection page</p>} />
        <Route path="/login" element={<p>Login page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("authentication pages and route guards", () => {
  beforeEach(() => {
    useAuth.mockReset();
  });

  it("submits valid login details and routes new users to interest selection", async () => {
    useAuth.mockReturnValue({
      loading: false,
      login: vi.fn().mockResolvedValue({ user: { interests: [] } }),
    });
    renderWithRoutes(<Login />);

    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: "reader@example.test" },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "securepass123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    expect(await screen.findByText("Interest selection page")).toBeInTheDocument();
  });

  it("shows a sign-in error returned by the API", async () => {
    useAuth.mockReturnValue({
      loading: false,
      login: vi.fn().mockRejectedValue({
        response: { data: { detail: "Invalid email or password" } },
      }),
    });
    renderWithRoutes(<Login />);
    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: "reader@example.test" },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "incorrect123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
  });

  it("submits registration fields and displays success", async () => {
    const register = vi.fn().mockResolvedValue({
      data: { message: "User registered successfully" },
    });
    useAuth.mockReturnValue({ loading: false, register });
    renderWithRoutes(<Register />);
    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: "Reader Person" },
    });
    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: "reader@example.test" },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "securepass123" },
    });
    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: "securepass123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Register" }));

    expect(await screen.findByText("User registered successfully")).toBeInTheDocument();
    expect(register).toHaveBeenCalledWith({
      full_name: "Reader Person",
      email: "reader@example.test",
      password: "securepass123",
      confirm_password: "securepass123",
    });
  });

  it("redirects unauthenticated users from protected pages to login", async () => {
    useAuth.mockReturnValue({ user: null, loading: false });
    renderWithRoutes(
      <ProtectedRoute>
        <p>Private account page</p>
      </ProtectedRoute>,
    );

    expect(await screen.findByText("Login page")).toBeInTheDocument();
    expect(screen.queryByText("Private account page")).not.toBeInTheDocument();
  });

  it("shows a loading state while the current session is being checked", async () => {
    useAuth.mockReturnValue({ user: null, loading: true });
    renderWithRoutes(
      <GuestRoute>
        <p>Guest content</p>
      </GuestRoute>,
    );

    await waitFor(() => expect(screen.getByText("Checking your session...")).toBeInTheDocument());
  });
});
