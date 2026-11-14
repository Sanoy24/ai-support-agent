const CATEGORY_LABELS: Record<string, string> = {
  refund: "Refund",
  cancellation: "Cancellation",
  order_change: "Order change",
  damaged_or_wrong_item: "Damaged or wrong item",
  complaint: "Complaint",
  customer_request: "Asked for a person",
  other: "Other",
};

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category.replaceAll("_", " ");
}
