// Example: Dynamically update milestone colors based on progress
var milestones = [
    { id: 1, status: 'completed' },  // Example: User Profile completed
    { id: 2, status: 'started' },    // Example: Registration started
    { id: 3, status: 'not-started' },// Example: Store Registration not started
    { id: 4, status: 'not-started' } // Example: Document Upload not started
];

milestones.forEach(function(milestone) {
    var element = document.getElementById('milestone-' + milestone.id);
    if (milestone.status === 'completed') {
        element.classList.add('completed');
    } else if (milestone.status === 'started') {
        element.classList.add('started');
    } else {
        element.classList.add('not-started');
    }
});



