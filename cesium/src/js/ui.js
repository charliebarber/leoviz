export const createEntityToggle = (entity, checkboxId) => {
  const checkbox = document.getElementById(checkboxId);

  checkbox.addEventListener('change', function () {
    if (checkbox.checked) {
        entity.show = true;
    } else {
        entity.show = false;
    }
  });
}