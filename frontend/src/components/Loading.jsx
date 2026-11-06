export default function Loading({ message = "Loading..." }) {
  return (
    <div className="flex min-h-[50vh] items-center justify-center px-6">
      <div className="flex items-center gap-3 rounded-full border border-stone-200 bg-white px-5 py-3 text-sm font-medium text-stone-600 shadow-sm">
        <span className="inline-block size-4 animate-spin rounded-full border-2 border-stone-300 border-t-green-700" />
        {message}
      </div>
    </div>
  );
}
